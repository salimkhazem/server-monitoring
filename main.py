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
            raise

def parse_nvidia_smi(output: str) -> List[Dict]:
    try:
        gpus = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
                
            parts = line.strip().split(',')
            if len(parts) >= 6:
                # Convert memory values to GB
                memory_used_mb = float(parts[2].strip())
                memory_total_mb = float(parts[3].strip())
                memory_used_gb = memory_used_mb / 1024
                memory_total_gb = memory_total_mb / 1024
                
                gpu = {
                    'id': parts[0].strip(),
                    'name': parts[1].strip(),
                    'memory_used': f"{memory_used_gb:.1f}G",
                    'memory_total': f"{memory_total_gb:.1f}G",
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
        # Force English locale for commands to ensure consistent parsing
        locale_prefix = "LC_ALL=C "
        
        # Get disk usage - get all partitions and ensure they include /mnt mounts
        stdin, stdout, stderr = client.exec_command(f"{locale_prefix}df -h | grep -v tmpfs | grep -v devtmpfs | grep -v snap | grep -v Filesystem", timeout=10)
        disk_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"Disk command stderr: {stderr_output}")
            
        # Also specifically check for disks mounted in /mnt
        stdin, stdout, stderr = client.exec_command(f"{locale_prefix}df -h | grep '/mnt'", timeout=10)
        mnt_disk_output = stdout.read().decode().strip()
        
        # Combine the outputs
        if mnt_disk_output and not mnt_disk_output in disk_output:
            disk_output = disk_output + "\n" + mnt_disk_output
        
        # Parse all disk partitions
        all_disks = []
        storage_disks = []
        total_storage_size = 0.0
        total_storage_used = 0.0
        total_storage_available = 0.0
        try:
            disk_lines = disk_output.strip().split('\n')
            for line in disk_lines:
                if not line.strip():
                    continue
                    
                disk_info = line.split()
                if len(disk_info) >= 6:  # Format: Filesystem Size Used Avail Use% Mounted
                    try:
                        # Extract usage percentage - handle different formats
                        usage_percent_str = disk_info[4].replace('%', '')
                        # Try to convert to int, default to 0 if it fails
                        try:
                            usage_percent = int(usage_percent_str)
                        except ValueError:
                            logger.warning(f"Could not parse disk usage percentage: {usage_percent_str}, defaulting to 0")
                            usage_percent = 0
                            
                        partition = {
                            'filesystem': disk_info[0],
                            'total': disk_info[1],
                            'used': disk_info[2],
                            'available': disk_info[3],
                            'usage_percent': usage_percent,
                            'mount_point': disk_info[5]
                        }
                        all_disks.append(partition)
                        
                        # Check if this is one of the storage disks we want
                        mount_point = disk_info[5]
                        if '/mnt/storage_1_10T' in mount_point or '/mnt/storage_2_10T' in mount_point or '/mnt/user_disk' in mount_point:
                            storage_disks.append(partition)
                            
                            # Try to convert sizes to numeric values for totals
                            try:
                                # Helper function to convert size strings like "11T", "944G", etc. to GB
                                def size_to_gb(size_str):
                                    if not size_str:
                                        return 0.0
                                    
                                    # Remove any non-numeric prefix
                                    numeric_part = ''.join(c for c in size_str if c.isdigit() or c == '.')
                                    if not numeric_part:
                                        return 0.0
                                    
                                    value = float(numeric_part)
                                    
                                    # Convert based on suffix
                                    if 'T' in size_str:
                                        return value * 1024  # TB to GB
                                    elif 'G' in size_str:
                                        return value  # Already GB
                                    elif 'M' in size_str:
                                        return value / 1024  # MB to GB
                                    elif 'K' in size_str:
                                        return value / (1024 * 1024)  # KB to GB
                                    else:
                                        return value  # Assume GB if no suffix
                                
                                # Add to totals
                                total_storage_size += size_to_gb(disk_info[1])
                                total_storage_used += size_to_gb(disk_info[2])
                                total_storage_available += size_to_gb(disk_info[3])
                            except Exception as e:
                                logger.warning(f"Error calculating storage totals: {str(e)}")
                    except Exception as e:
                        logger.warning(f"Error parsing disk line: {line}, error: {str(e)}")
                        continue
            
            # Calculate storage usage percentage
            storage_usage_percent = 0
            if total_storage_size > 0:
                storage_usage_percent = round((total_storage_used / total_storage_size) * 100, 1)
            
            # Convert GB to TB for the summary
            total_storage_size_tb = total_storage_size / 1024
            total_storage_used_tb = total_storage_used / 1024
            total_storage_available_tb = total_storage_available / 1024
            
            # Create a summary disk object for all storage
            storage_summary = {
                'total': f"{total_storage_size_tb:.1f}T",
                'used': f"{total_storage_used_tb:.1f}T",
                'available': f"{total_storage_available_tb:.1f}T",
                'usage_percent': storage_usage_percent
            }
            
            # If no disks were found, add a placeholder
            if not all_disks:
                all_disks.append({
                    'filesystem': 'N/A',
                    'total': 'N/A',
                    'used': 'N/A',
                    'available': 'N/A',
                    'usage_percent': 0,
                    'mount_point': '/'
                })
                
            # Maintain backwards compatibility - keep the root disk (/) as 'disk'
            root_disk = next((disk for disk in all_disks if disk['mount_point'] == '/'), None)
            if root_disk:
                disk_usage = {
                    'total': root_disk['total'],
                    'used': root_disk['used'],
                    'available': root_disk['available'],
                    'usage_percent': root_disk['usage_percent']
                }
            elif all_disks:
                disk_usage = {
                    'total': all_disks[0]['total'],
                    'used': all_disks[0]['used'],
                    'available': all_disks[0]['available'],
                    'usage_percent': all_disks[0]['usage_percent']
                }
            else:
                disk_usage = {
                    'total': 'N/A',
                    'used': 'N/A',
                    'available': 'N/A',
                    'usage_percent': 0
                }
        except Exception as e:
            logger.warning(f"Failed to parse disk info: {str(e)}")
            logger.warning(traceback.format_exc())
            all_disks = []
            storage_disks = []
            storage_summary = {
                'total': '0G',
                'used': '0G',
                'available': '0G',
                'usage_percent': 0
            }
            disk_usage = {
                'total': 'N/A',
                'used': 'N/A',
                'available': 'N/A',
                'usage_percent': 0
            }
        
        # Get memory usage
        stdin, stdout, stderr = client.exec_command(f"{locale_prefix}free -m | grep Mem", timeout=10)
        memory_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"Memory command stderr: {stderr_output}")
        
        # Safely parse memory info and convert to GB
        try:
            memory_info = memory_output.split()
            if len(memory_info) >= 4:
                total_mb = int(memory_info[1])
                used_mb = int(memory_info[2])
                free_mb = int(memory_info[3])
                
                # Convert to GB
                total_gb = total_mb / 1024
                used_gb = used_mb / 1024
                free_gb = free_mb / 1024
                
                memory_usage = {
                    'total': f"{total_gb:.1f}G",
                    'used': f"{used_gb:.1f}G",
                    'free': f"{free_gb:.1f}G",
                    'usage_percent': round((used_mb / total_mb) * 100, 1) if total_mb > 0 else 0
                }
            else:
                logger.warning(f"Unexpected memory info format: {memory_output}")
                memory_usage = {
                    'total': '0G',
                    'used': '0G',
                    'free': '0G',
                    'usage_percent': 0
                }
        except Exception as e:
            logger.warning(f"Failed to parse memory info: {str(e)}")
            memory_usage = {
                'total': '0G',
                'used': '0G',
                'free': '0G',
                'usage_percent': 0
            }
        
        # Get more accurate CPU usage
        stdin, stdout, stderr = client.exec_command(f"{locale_prefix}top -bn1 | head -5 | grep -i cpu", timeout=10)
        cpu_output = stdout.read().decode().strip()
        stderr_output = stderr.read().decode()
        if stderr_output:
            logger.warning(f"CPU command stderr: {stderr_output}")
        
        # Safely parse CPU usage
        try:
            # Look for idle percentage in CPU output
            import re
            matches = re.search(r"(\d+\.\d+)\s*id", cpu_output)
            if matches:
                idle_percent = float(matches.group(1))
                cpu_usage = round(100.0 - idle_percent, 1)
            else:
                # Fallback method
                stdin, stdout, stderr = client.exec_command(f"{locale_prefix}top -bn1 | grep \"Cpu(s)\" | sed \"s/.*, *\\([0-9.]*\\)%* id.*/\\1/\" | awk '{{print 100 - $1}}'", timeout=10)
                cpu_output = stdout.read().decode().strip()
                cpu_usage = float(cpu_output) if cpu_output else 0
        except Exception as e:
            logger.warning(f"Failed to parse CPU usage: {str(e)}")
            cpu_usage = 0
        
        # Try to get CPU cores using nproc instead of lscpu
        stdin, stdout, stderr = client.exec_command(f"{locale_prefix}nproc", timeout=10)
        cpu_cores_output = stdout.read().decode().strip()
        
        if cpu_cores_output and cpu_cores_output.isdigit():
            cpu_info = f"{cpu_cores_output} cores"
        else:
            # Fallback to lscpu if nproc fails
            stdin, stdout, stderr = client.exec_command(f"{locale_prefix}lscpu | grep \"^CPU(s):\" | head -1", timeout=10)
            cpu_info_output = stdout.read().decode().strip()
            
            try:
                if ':' in cpu_info_output:
                    cpu_info = cpu_info_output.split(':')[1].strip() + " cores"
                else:
                    # Try another approach
                    stdin, stdout, stderr = client.exec_command(f"{locale_prefix}grep -c processor /proc/cpuinfo", timeout=10)
                    processor_count = stdout.read().decode().strip()
                    if processor_count and processor_count.isdigit():
                        cpu_info = f"{processor_count} cores"
                    else:
                        cpu_info = 'N/A'
                        logger.warning(f"CPU info format unexpected: {cpu_info_output}")
            except Exception as e:
                cpu_info = 'N/A'
                logger.warning(f"Failed to parse CPU info: {str(e)}")
        
        return {
            'disk': disk_usage,
            'all_disks': all_disks,
            'storage_disks': storage_disks,
            'storage_summary': storage_summary,
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
            'all_disks': [],
            'storage_disks': [],
            'storage_summary': {'total': '0G', 'used': '0G', 'available': '0G', 'usage_percent': 0},
            'memory': {'total': '0G', 'used': '0G', 'free': '0G', 'usage_percent': 0},
            'cpu': {'usage_percent': 0, 'cores': 'N/A'}
        }

def get_user_resources(client: paramiko.SSHClient) -> List[Dict]:
    """Get resource usage for each active user"""
    try:
        locale_prefix = "LC_ALL=C "
        active_users = []
        
        # Get list of active users
        stdin, stdout, stderr = client.exec_command(f"{locale_prefix}who", timeout=10)
        who_output = stdout.read().decode().strip()
        
        # Parse the who output to get usernames
        usernames = set()
        for line in who_output.split('\n'):
            if line.strip():
                parts = line.split()
                if parts:
                    usernames.add(parts[0])
        
        # For each user, get resource usage
        for username in usernames:
            # Get CPU and memory usage with ps
            cmd = f"{locale_prefix}ps aux | grep ^{username} | awk '{{cpu_sum += $3; mem_sum += $4}} END {{print cpu_sum, mem_sum}}'"
            stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
            ps_output = stdout.read().decode().strip()
            
            cpu_usage = 0.0
            memory_usage = 0.0
            
            if ps_output:
                try:
                    parts = ps_output.split()
                    if len(parts) >= 2:
                        cpu_usage = float(parts[0])
                        memory_usage = float(parts[1])
                except Exception as e:
                    logger.warning(f"Error parsing ps output for user {username}: {str(e)}")
            
            # Get GPU usage with nvidia-smi
            cmd = f"{locale_prefix}nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits"
            stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
            nvidia_output = stdout.read().decode().strip()
            
            # Get PIDs owned by this user
            cmd = f"{locale_prefix}ps -u {username} -o pid= | tr '\n' ',' | sed 's/,$//'"
            stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
            user_pids = stdout.read().decode().strip().split(',')
            
            gpu_memory_usage = 0
            
            # Parse nvidia-smi output and match PIDs to this user
            if nvidia_output and user_pids:
                for line in nvidia_output.split('\n'):
                    if not line.strip():
                        continue
                        
                    parts = line.split(',')
                    if len(parts) >= 2:
                        pid = parts[0].strip()
                        if pid in user_pids:
                            try:
                                memory = int(parts[1].strip())
                                gpu_memory_usage += memory
                            except Exception as e:
                                logger.warning(f"Error parsing GPU memory for PID {pid}: {str(e)}")
            
            # Get storage usage with du
            cmd = f"{locale_prefix}du -s /home/{username} 2>/dev/null || echo '0'"
            stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
            storage_output = stdout.read().decode().strip()
            
            storage_usage = 0
            if storage_output:
                try:
                    storage_usage = int(storage_output.split()[0]) / (1024 * 1024)  # Convert KB to GB
                except Exception as e:
                    logger.warning(f"Error parsing storage usage for user {username}: {str(e)}")
            
            # Create user resource dict
            user_resources = {
                'username': username,
                'cpu_usage': round(cpu_usage, 1),
                'memory_usage': round(memory_usage, 1),
                'gpu_memory_usage': gpu_memory_usage,
                'storage_usage': round(storage_usage, 2),
                'sessions': []
            }
            
            # Add session details
            for line in who_output.split('\n'):
                if line.strip() and line.split()[0] == username:
                    try:
                        parts = line.split()
                        session = {
                            'terminal': parts[1] if len(parts) > 1 else 'N/A',
                            'date': ' '.join(parts[2:5]) if len(parts) > 4 else 'N/A',
                            'from': parts[5].strip('()') if len(parts) > 5 and '(' in parts[5] else 'N/A'
                        }
                        user_resources['sessions'].append(session)
                    except Exception as e:
                        logger.warning(f"Error parsing session info for {username}: {str(e)}")
            
            active_users.append(user_resources)
        
        return active_users
    except Exception as e:
        logger.error(f"Error getting user resources: {str(e)}")
        logger.error(traceback.format_exc())
        return []

@app.get("/api/gpu-status")
async def get_gpu_status():
    """
    Get GPU status information via SSH connection.
    """
    ssh_config = SSHConfig()
    client = None
    
    try:
        # Try to get SSH client
        client = ssh_config.get_client()
        
        # Get GPU information
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
        
        # Get user resources
        logger.info("Getting user resources")
        user_resources = get_user_resources(client)
        
        gpus = parse_nvidia_smi(gpu_info)
        
        return {
            "gpus": gpus,
            "active_users": user_info.strip().split('\n'),
            "user_resources": user_resources,
            "system_resources": system_resources
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_gpu_status: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
    finally:
        if client:
            client.close()
            logger.info("SSH connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 