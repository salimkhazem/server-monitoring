# Server Resource Monitor

A web application to monitor server resources (GPU, CPU, memory, disk) and user information on a remote server via SSH.

## Features

- Real-time GPU monitoring (memory usage, temperature, power usage)
- System resource monitoring:
  - CPU usage and core count
  - Memory usage (used/total)
  - Disk usage (used/total)
- User tracking (who is using which GPU)
- Modern, responsive UI with dark theme
- Auto-refreshing data (every 5 seconds)

## Prerequisites

- Python 3.8+
- Node.js 14+
- Access to a server with NVIDIA GPUs
- SSH access to the server
- Server must have standard Linux commands available (`df`, `free`, `top`, `lscpu`)

## Setup for Local Development

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/server-resource-monitor.git
   cd server-resource-monitor
   ```

2. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```

4. Edit the `.env` file with your SSH server details:
   ```
   SSH_HOST=your-server-hostname
   SSH_USERNAME=your-username
   SSH_PASSWORD=your-password
   # Or use SSH key authentication (recommended)
   # SSH_KEY_FILE=/path/to/your/private/key
   ```

5. Install frontend dependencies and set up environment:
   ```bash
   cd frontend
   cp .env.example .env
   npm install
   ```

## Running the Application Locally

1. Start the backend server:
   ```bash
   python main.py
   ```

2. In a new terminal, start the frontend development server:
   ```bash
   cd frontend
   npm start
   ```

3. Open your browser and navigate to `http://localhost:3000`


1. Clone the repository on your new machine
2. Follow the setup steps above, updating the `.env` file with your new server's credentials
3. If the server has a different configuration, you might need to update the commands in `main.py` to match the available commands on your server

## Security Notes

- The application uses environment variables for sensitive information
- SSH key authentication is recommended over password authentication
- Make sure to keep your `.env` file secure and never commit it to version control
- When deploying to Azure, use secure methods to set environment variables
- Consider using Azure Key Vault for storing sensitive credentials

## Troubleshooting

- If you can't connect to the server, check your SSH credentials in the `.env` file
- Make sure the server has `nvidia-smi` installed and accessible
- Check that your user has permissions to execute `nvidia-smi`, `df`, `free`, `top`, `lscpu`, and `who` commands
- If system resource commands fail, ensure your user has the necessary permissions to access system information
- For Azure deployments, check the App Service logs for backend issues
- For frontend issues, check the browser console and network tab for errors 
