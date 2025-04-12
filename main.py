from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import paramiko
import json
from typing import List, Dict
import os
from dotenv import load_dotenv
import traceback
import logging
import socket
import time
import base64
import tempfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SSHConfig:
    def __init__(self):
        self.hostname = os.getenv("SSH_HOST")
        self.username = os.getenv("SSH_USERNAME")
        self.password = os.getenv("SSH_PASSWORD")
        self.key_filename = os.getenv("SSH_KEY_FILE")
        self.key_content = os.getenv("SSH_KEY_CONTENT")
        
        logger.info(f"SSH Config: host={self.hostname}, user={self.username}, key_file={self.key_filename}")

    def get_client(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Set connection timeout
        socket.setdefaulttimeout(10)
        
        try:
            # Handle SSH key as file
            if self.key_filename:
                logger.info(f"Connecting with key file: {self.key_filename}")
                # Expand the home directory if needed
                key_path = os.path.expanduser(self.key_filename)
                logger.info(f"Expanded key path: {key_path}")
                
                if not os.path.exists(key_path):
                    logger.error(f"SSH key file not found: {key_path}")
                    raise FileNotFoundError(f"SSH key file not found: {key_path}")
                
                client.connect(
                    hostname=self.hostname,
                    username=self.username,
                    key_filename=key_path,
                    timeout=10,
                    banner_timeout=10
                )
            # Handle SSH key as content in environment variable
            elif self.key_content:
                logger.info("Connecting with key content from environment variable")
                try:
                    # Decode base64 encoded key content
                    key_data = base64.b64decode(self.key_content).decode('utf-8')
                    
                    # Create a temporary file to store the key
                    with tempfile.NamedTemporaryFile(delete=False) as key_file:
                        key_file.write(key_data.encode('utf-8'))
                        key_path = key_file.name
                    
                    # Set proper permissions on the key file
                    os.chmod(key_path, 0o600)
                    
                    try:
                        client.connect(
                            hostname=self.hostname,
                            username=self.username,
                            key_filename=key_path,
                            timeout=10,
                            banner_timeout=10
                        )
                    finally:
                        # Clean up the temporary file
                        os.unlink(key_path)
                        
                except Exception as e:
                    logger.error(f"Error processing SSH key content: {str(e)}")
                    raise
            else:
                logger.info("Connecting with password")
                client.connect(
                    hostname=self.hostname,
                    username=self.username,
                    password=self.password,
                    timeout=10,
                    banner_timeout=10
                )
            logger.info("SSH connection successful")
            return client
        except Exception as e:
            logger.error(f"SSH connection failed: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"SSH connection failed: {str(e)}")

def parse_nvidia_smi(output: str) -> List[Dict]:
    try:
        gpus = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            parts = line.strip().split(',')
            if len(parts) >= 6:
                gpu = {
                    'id': parts[0].strip(),
                    'name': parts[1].strip(),
                    'memory_used': parts[2].strip(),
                    'memory_total': parts[3].strip(),
                    'temperature': parts[4].strip(),
                    'power_usage': parts[5].strip(),
                    'processes': 'N/A',
                    'user': 'N/A'
                }
                gpus.append(gpu)
        
        return gpus
    except Exception as e:
        logger.error(f"Error parsing nvidia-smi output: {str(e)}")
        logger.error(f"Output was: {output}")
        logger.error(traceback.format_exc())
        return []

def get_system_resources(client: paramiko.SSHClient) -> Dict:
    try:
        # Get disk usage
        stdin, stdout, stderr = client.exec_command('df -h / | tail -1', timeout=10)
        disk_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"Disk command stderr: {stderr_output}")
        
        # Safely parse disk info
        try:
            disk_info = disk_output.split()
            if len(disk_info) >= 5:
                disk_usage = {
                    'total': disk_info[1],
                    'used': disk_info[2],
                    'available': disk_info[3],
                    'usage_percent': int(disk_info[4].replace('%', ''))
                }
            else:
                logger.warning(f"Unexpected disk info format: {disk_output}")
                disk_usage = {
                    'total': 'N/A',
                    'used': 'N/A',
                    'available': 'N/A',
                    'usage_percent': 0
                }
        except Exception as e:
            logger.warning(f"Failed to parse disk info: {str(e)}")
            disk_usage = {
                'total': 'N/A',
                'used': 'N/A',
                'available': 'N/A',
                'usage_percent': 0
            }
        
        # Get memory usage
        stdin, stdout, stderr = client.exec_command('free -m | grep Mem', timeout=10)
        memory_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"Memory command stderr: {stderr_output}")
        
        # Safely parse memory info
        try:
            memory_info = memory_output.split()
            if len(memory_info) >= 4:
                memory_usage = {
                    'total': int(memory_info[1]),
                    'used': int(memory_info[2]),
                    'free': int(memory_info[3]),
                    'usage_percent': round((int(memory_info[2]) / int(memory_info[1])) * 100, 2) if int(memory_info[1]) > 0 else 0
                }
            else:
                logger.warning(f"Unexpected memory info format: {memory_output}")
                memory_usage = {
                    'total': 0,
                    'used': 0,
                    'free': 0,
                    'usage_percent': 0
                }
        except Exception as e:
            logger.warning(f"Failed to parse memory info: {str(e)}")
            memory_usage = {
                'total': 0,
                'used': 0,
                'free': 0,
                'usage_percent': 0
            }
        
        # Get CPU usage
        stdin, stdout, stderr = client.exec_command('top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk \'{print 100 - $1}\'', timeout=10)
        cpu_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"CPU command stderr: {stderr_output}")
        
        # Safely parse CPU usage
        try:
            cpu_usage = float(cpu_output) if cpu_output else 0
        except Exception as e:
            logger.warning(f"Failed to parse CPU usage: {str(e)}")
            cpu_usage = 0
        
        # Get CPU info
        stdin, stdout, stderr = client.exec_command('lscpu | grep "CPU(s):" | head -1', timeout=10)
        cpu_info_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"CPU info command stderr: {stderr_output}")
        
        # Safely parse CPU info
        try:
            if ':' in cpu_info_output:
                cpu_info = cpu_info_output.split(':')[1].strip()
            else:
                cpu_info = 'N/A'
                logger.warning(f"CPU info format unexpected: {cpu_info_output}")
        except Exception as e:
            cpu_info = 'N/A'
            logger.warning(f"Failed to parse CPU info: {str(e)}")
        
        return {
            'disk': disk_usage,
            'memory': memory_usage,
            'cpu': {
                'usage_percent': cpu_usage,
                'cores': cpu_info
            }
        }
    except Exception as e:
        logger.error(f"Error getting system resources: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'disk': {'total': 'N/A', 'used': 'N/A', 'available': 'N/A', 'usage_percent': 0},
            'memory': {'total': 0, 'used': 0, 'free': 0, 'usage_percent': 0},
            'cpu': {'usage_percent': 0, 'cores': 'N/A'}
        }

@app.get("/api/gpu-status")
async def get_gpu_status():
    ssh_config = SSHConfig()
    client = None
    
    try:
        client = ssh_config.get_client()
        
        # Get GPU information - using valid fields
        logger.info("Executing nvidia-smi command")
        stdin, stdout, stderr = client.exec_command('nvidia-smi --query-gpu=index,name,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits', timeout=10)
        gpu_info = stdout.read().decode()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"nvidia-smi stderr: {stderr_output}")
        
        # Get user information
        logger.info("Executing who command")
        stdin, stdout, stderr = client.exec_command('who', timeout=10)
        user_info = stdout.read().decode()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"who command stderr: {stderr_output}")
        
        # Get system resources
        logger.info("Getting system resources")
        system_resources = get_system_resources(client)
        
        gpus = parse_nvidia_smi(gpu_info)
        
        return {
            "gpus": gpus,
            "active_users": user_info.strip().split('\n'),
            "system_resources": system_resources
        }
    except Exception as e:
        logger.error(f"Error in get_gpu_status: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if client:
            client.close()
            logger.info("SSH connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 