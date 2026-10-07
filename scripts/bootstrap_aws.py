import json
from pathlib import Path
import time

import boto3
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local-cp2"
ACCOUNT = "026343683449"
REGION = "us-east-1"
BUCKET = "income-lab-day21-026343683449"
TAGS = [{"Key": "Project", "Value": "income-lab-day21"}]


def ensure_role(iam, name, principal, policy_name):
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": principal, "Action": "sts:AssumeRole"}]}
    try:
        role = iam.get_role(RoleName=name)["Role"]
        if not any(tag == TAGS[0] for tag in role.get("Tags", [])):
            raise RuntimeError(f"Refusing to modify an unrelated role: {name}")
    except iam.exceptions.NoSuchEntityException:
        role = iam.create_role(RoleName=name, AssumeRolePolicyDocument=json.dumps(trust), Tags=TAGS)["Role"]
    policy = json.loads((ROOT / "deploy/aws" / policy_name).read_text())
    iam.put_role_policy(RoleName=name, PolicyName="IncomeLabScopedS3", PolicyDocument=json.dumps(policy))
    return role["Arn"]


def assume_setup(session, role_arn):
    sts = session.client("sts")
    for attempt in range(12):
        try:
            credentials = sts.assume_role(RoleArn=role_arn, RoleSessionName="IncomeLabSetup")["Credentials"]
            return boto3.Session(aws_access_key_id=credentials["AccessKeyId"], aws_secret_access_key=credentials["SecretAccessKey"], aws_session_token=credentials["SessionToken"], region_name=REGION)
        except sts.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "AccessDenied" or attempt == 11:
                raise
            time.sleep(5)


def ensure_actions_user(iam):
    name = "income-lab-day21-actions"
    try:
        user = iam.get_user(UserName=name)["User"]
        if not any(tag == TAGS[0] for tag in user.get("Tags", [])):
            raise RuntimeError(f"Refusing to modify an unrelated IAM user: {name}")
    except iam.exceptions.NoSuchEntityException:
        iam.create_user(UserName=name, Tags=TAGS)
    policy = json.loads((ROOT / "deploy/aws/actions-policy.json").read_text())
    iam.put_user_policy(UserName=name, PolicyName="IncomeLabScopedS3", PolicyDocument=json.dumps(policy))
    key_path = LOCAL / "storage-credentials.json"
    if not key_path.exists():
        if iam.list_access_keys(UserName=name)["AccessKeyMetadata"]:
            raise RuntimeError("Actions user already has an access key; reuse its local credentials or rotate explicitly.")
        key = iam.create_access_key(UserName=name)["AccessKey"]
        key_path.write_text(json.dumps({"aws_access_key_id": key["AccessKeyId"], "aws_secret_access_key": key["SecretAccessKey"]}), encoding="utf-8")
    return name


def ensure_ssh_key(ec2):
    private_path = LOCAL / "income_deploy"
    public_path = LOCAL / "income_deploy.pub"
    if not private_path.exists():
        key = Ed25519PrivateKey.generate()
        private_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()))
        public_path.write_bytes(key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH))
    name = "income-lab-day21-deploy"
    try:
        existing = ec2.describe_key_pairs(KeyNames=[name], IncludePublicKey=True)["KeyPairs"][0]
        if existing.get("PublicKey", "").split()[:2] != public_path.read_text().split()[:2]:
            raise RuntimeError("Existing EC2 key pair does not match the local deployment key.")
    except ec2.exceptions.ClientError as error:
        if error.response["Error"]["Code"] != "InvalidKeyPair.NotFound":
            raise
        ec2.import_key_pair(KeyName=name, PublicKeyMaterial=public_path.read_bytes(), TagSpecifications=[{"ResourceType": "key-pair", "Tags": TAGS}])
    return name


def user_data():
    import base64
    code = base64.b64encode((ROOT / "src/serve.py").read_bytes()).decode()
    requirements = base64.b64encode((ROOT / "requirements-serving.txt").read_bytes()).decode()
    return f'''#!/bin/bash
set -eux
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3-venv python3-pip
install -d -o ubuntu -g ubuntu /home/ubuntu/income-lab/src /home/ubuntu/models
printf '%s' '{code}' | base64 -d > /home/ubuntu/income-lab/src/serve.py
printf '%s' '{requirements}' | base64 -d > /home/ubuntu/income-lab/requirements-serving.txt
chown -R ubuntu:ubuntu /home/ubuntu/income-lab
sudo -u ubuntu python3 -m venv /home/ubuntu/income-lab/.venv
sudo -u ubuntu /home/ubuntu/income-lab/.venv/bin/python -m pip install -r /home/ubuntu/income-lab/requirements-serving.txt
cat > /etc/systemd/system/income-api.service <<'EOF'
[Unit]
Description=Income Model Inference Server
After=network-online.target
Wants=network-online.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/income-lab
Environment="ARTIFACT_BUCKET={BUCKET}"
Environment="AWS_DEFAULT_REGION={REGION}"
ExecStart=/home/ubuntu/income-lab/.venv/bin/python /home/ubuntu/income-lab/src/serve.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable income-api
'''


def main():
    LOCAL.mkdir(exist_ok=True)
    session = boto3.Session(profile_name="lab16", region_name=REGION)
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != ACCOUNT:
        raise RuntimeError("AWS account does not match the reviewed lab policies.")
    iam = session.client("iam")
    setup_arn = ensure_role(iam, "income-lab-day21-setup", {"AWS": identity["Arn"]}, "setup-policy.json")
    setup = assume_setup(session, setup_arn)
    s3 = setup.client("s3")
    existing = LOCAL / "resources.json"
    if existing.exists():
        state = json.loads(existing.read_text())
    else:
        state = {"account": ACCOUNT, "region": REGION, "bucket": BUCKET, "setup_role_arn": setup_arn}
    if not state.get("bucket_created"):
        s3.create_bucket(Bucket=BUCKET)
        state["bucket_created"] = True
        existing.write_text(json.dumps(state, indent=2))
    s3.put_public_access_block(Bucket=BUCKET, PublicAccessBlockConfiguration={"BlockPublicAcls": True, "IgnorePublicAcls": True, "BlockPublicPolicy": True, "RestrictPublicBuckets": True})
    s3.put_bucket_encryption(Bucket=BUCKET, ServerSideEncryptionConfiguration={"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]})
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps({"Version": "2012-10-17", "Statement": [{"Effect": "Deny", "Principal": "*", "Action": "s3:*", "Resource": [f"arn:aws:s3:::{BUCKET}", f"arn:aws:s3:::{BUCKET}/*"], "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}))
    state["actions_user"] = ensure_actions_user(iam)
    role_name = "income-api-day21"
    ensure_role(iam, role_name, {"Service": "ec2.amazonaws.com"}, "serve-policy.json")
    try:
        profile = iam.get_instance_profile(InstanceProfileName=role_name)["InstanceProfile"]
    except iam.exceptions.NoSuchEntityException:
        profile = iam.create_instance_profile(InstanceProfileName=role_name, Tags=TAGS)["InstanceProfile"]
    if not profile["Roles"]:
        iam.add_role_to_instance_profile(InstanceProfileName=role_name, RoleName=role_name)
    ec2 = session.client("ec2")
    key_name = ensure_ssh_key(ec2)
    if not state.get("instance_id"):
        vpcs = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])["Vpcs"]
        if len(vpcs) != 1:
            raise RuntimeError("A default VPC is required; choose a public subnet explicitly if none exists.")
        vpc = vpcs[0]["VpcId"]
        subnets = ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc]}, {"Name": "default-for-az", "Values": ["true"]}])["Subnets"]
        offerings = ec2.describe_instance_type_offerings(LocationType="availability-zone", Filters=[{"Name": "instance-type", "Values": ["t3.micro"]}])["InstanceTypeOfferings"]
        supported_zones = {entry["Location"] for entry in offerings}
        subnets = sorted((subnet for subnet in subnets if subnet["AvailabilityZone"] in supported_zones), key=lambda subnet: subnet["AvailabilityZone"])
        if not subnets:
            raise RuntimeError("No public default subnet available.")
        groups = ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc]}, {"Name": "group-name", "Values": ["income-api-day21"]}])["SecurityGroups"]
        if groups:
            group_id = groups[0]["GroupId"]
        else:
            group_id = ec2.create_security_group(GroupName="income-api-day21", Description="Day21 income inference lab", VpcId=vpc, TagSpecifications=[{"ResourceType": "security-group", "Tags": TAGS}])["GroupId"]
            # Public SSH is needed for the lab's GitHub-hosted SSH deployment runner.
            ec2.authorize_security_group_ingress(GroupId=group_id, IpPermissions=[{"IpProtocol": "tcp", "FromPort": port, "ToPort": port, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": description}]} for port, description in [(22, "Lab SSH deployment"), (8080, "Lab income API")]])
        images = ec2.describe_images(Owners=["099720109477"], Filters=[{"Name": "name", "Values": ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]}, {"Name": "state", "Values": ["available"]}])["Images"]
        image = max(images, key=lambda entry: entry["CreationDate"])
        time.sleep(10)
        instance = ec2.run_instances(ImageId=image["ImageId"], InstanceType="t3.micro", MinCount=1, MaxCount=1, KeyName=key_name, IamInstanceProfile={"Name": role_name}, NetworkInterfaces=[{"DeviceIndex": 0, "SubnetId": subnets[0]["SubnetId"], "Groups": [group_id], "AssociatePublicIpAddress": True}], MetadataOptions={"HttpTokens": "required", "HttpEndpoint": "enabled", "HttpPutResponseHopLimit": 1}, CreditSpecification={"CpuCredits": "standard"}, BlockDeviceMappings=[{"DeviceName": image["RootDeviceName"], "Ebs": {"VolumeSize": 12, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True}}], UserData=user_data(), TagSpecifications=[{"ResourceType": "instance", "Tags": TAGS + [{"Key": "Name", "Value": "income-api-day21"}]}, {"ResourceType": "volume", "Tags": TAGS}], ClientToken="income-lab-day21-initial")["Instances"][0]
        state.update(instance_id=instance["InstanceId"], security_group_id=group_id, key_name=key_name, instance_profile=role_name)
        existing.write_text(json.dumps(state, indent=2))
    ec2.get_waiter("instance_running").wait(InstanceIds=[state["instance_id"]], WaiterConfig={"Delay": 5, "MaxAttempts": 24})
    instance = ec2.describe_instances(InstanceIds=[state["instance_id"]])["Reservations"][0]["Instances"][0]
    state.update(server_host=instance["PublicIpAddress"], server_user="ubuntu")
    existing.write_text(json.dumps(state, indent=2))
    print(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
