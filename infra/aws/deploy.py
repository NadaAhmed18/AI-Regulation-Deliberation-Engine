"""
AWS Lifecycle & Seed Controller for AI Regulation Engine
Usage:
    python deploy.py deploy        - Creates VPC, Storage & App instances
    python deploy.py seed          - Runs import_db_from_json.py into the cloud Neo4j instance
    python deploy.py stop-storage  - Shuts down Storage EC2 to save compute money
    python deploy.py start-storage - Boots Storage EC2 back up
    python deploy.py status        - Displays current IPs and URLs
    python deploy.py destroy       - 100% clean teardown (leaves ZERO resources)
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

STACK_NAME = "ai-regulation-cloud"
REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "cloudformation.yaml"


def run_cmd(cmd: list[str], capture: bool = False) -> str:
    res = subprocess.run(cmd, capture_output=capture, text=True, shell=True)
    if res.returncode != 0 and capture:
        raise RuntimeError(f"Command failed: {res.stderr}")
    return res.stdout.strip() if capture else ""


def get_stack_outputs() -> dict[str, str]:
    cmd = (
        f"aws cloudformation describe-stacks --stack-name {STACK_NAME} "
        f"--region {REGION} --query \"Stacks[0].Outputs\" --output json"
    )
    raw = run_cmd(cmd, capture=True)
    if not raw or raw == "null":
        return {}
    outputs = json.loads(raw)
    return {item["OutputKey"]: item["OutputValue"] for item in outputs}


def deploy():
    print(f"[*] Deploying CloudFormation stack: {STACK_NAME} in {REGION}...")
    cmd = (
        f"aws cloudformation deploy "
        f"--template-file \"{TEMPLATE_PATH}\" "
        f"--stack-name {STACK_NAME} "
        f"--region {REGION} "
        f"--capabilities CAPABILITY_IAM"
    )
    subprocess.run(cmd, shell=True, check=True)

    print("\n[+] CloudFormation Stack deployed successfully!")
    outputs = get_stack_outputs()
    app_ip = outputs.get("AppPublicIP")
    print("=" * 60)
    print(f" Frontend App URL:  http://{app_ip}:5000")
    print(f" Backend Docs URL:  http://{app_ip}:8000/docs")
    print(f" Storage Instance:  {outputs.get('StorageInstanceId')}")
    print("=" * 60)
    print("\n[*] Waiting 45 seconds for Docker & databases to initialize on EC2...")
    time.sleep(45)
    print("\n[!] Next Step: Seed Neo4j data with: python infra/aws/deploy.py seed")


def seed_database():
    """Runs import_db_from_json.py pointing directly to the cloud Neo4j instance."""
    outputs = get_stack_outputs()
    app_ip = outputs.get("AppPublicIP")
    if not app_ip:
        print("[-] Could not retrieve App Public IP. Is the stack deployed?")
        return

    # In our VPC, the storage instance is at 10.0.1.50
    # We execute import_db_from_json with NEO4J_URI set
    print("[*] Preparing to seed Neo4j knowledge graph data from data/dump/neo4j_export.json...")
    
    # We can invoke the import script via Python by temporarily overriding environment variables
    os.environ["NEO4J_URI"] = f"bolt://{app_ip}:7687"
    os.environ["NEO4J_USERNAME"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "password123"

    sys.path.insert(0, str(BASE_DIR / "backend"))
    try:
        from src.scripts.import_db_from_json import import_database
        import_database()
        print("[+] Knowledge Graph data successfully injected into Cloud Neo4j!")
    except Exception as e:
        print(f"[-] Import failed: {e}")
        print("[*] Note: Ensure the Storage Layer ports are accessible or port-forwarded.")


def stop_storage():
    outputs = get_stack_outputs()
    storage_id = outputs.get("StorageInstanceId")
    if not storage_id:
        print("[-] Storage instance ID not found.")
        return
    print(f"[*] Stopping Storage Instance ({storage_id}) to save compute costs...")
    run_cmd(f"aws ec2 stop-instances --instance-ids {storage_id} --region {REGION}")
    print("[+] Storage instance is shutting down. Your EBS volume & data remain safe.")


def start_storage():
    outputs = get_stack_outputs()
    storage_id = outputs.get("StorageInstanceId")
    if not storage_id:
        print("[-] Storage instance ID not found.")
        return
    print(f"[*] Starting Storage Instance ({storage_id})...")
    run_cmd(f"aws ec2 start-instances --instance-ids {storage_id} --region {REGION}")
    print("[+] Storage instance is starting. It keeps its fixed private IP (10.0.1.50).")


def destroy():
    print("=" * 60)
    print(f" WARNING: Teardown will delete the ENTIRE stack: {STACK_NAME}")
    print(" - All EC2 Instances & Volumes will be terminated.")
    print(" - VPC, Security Groups, and Routes will be removed.")
    print(" - Zero residual AWS resources or charges will remain.")
    print("=" * 60)
    confirm = input("Are you sure you want to proceed? (y/N): ").strip().lower()
    if confirm != "y":
        print("Teardown cancelled.")
        return

    print(f"[*] Deleting CloudFormation stack: {STACK_NAME}...")
    run_cmd(f"aws cloudformation delete-stack --stack-name {STACK_NAME} --region {REGION}")
    print("[*] Waiting for resources to be completely deleted (this takes ~2-3 mins)...")
    run_cmd(f"aws cloudformation wait stack-delete-complete --stack-name {STACK_NAME} --region {REGION}")
    print("[+] Clean teardown complete! Zero resources left on your AWS account.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "deploy":
        deploy()
    elif action == "seed":
        seed_database()
    elif action == "stop-storage":
        stop_storage()
    elif action == "start-storage":
        start_storage()
    elif action == "destroy":
        destroy()
    else:
        outs = get_stack_outputs()
        if outs:
            print(json.dumps(outs, indent=2))
        else:
            print("[-] Stack is not currently deployed.")