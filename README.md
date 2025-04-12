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

## Deployment to Azure

### Option 1: Containerized Deployment (Recommended)

This repository includes Docker configuration and deployment scripts for easy deployment to Azure using containers.

1. Make the deployment script executable:
   ```bash
   chmod +x deploy-to-azure.sh
   ```

2. Run the deployment script:
   ```bash
   ./deploy-to-azure.sh
   ```
   
   Follow the prompts to enter your SSH credentials. The script will:
   - Create necessary Azure resources (Resource Group, Container Registry, App Service Plan)
   - Build and push Docker images for both frontend and backend
   - Deploy both services to Azure App Service
   - Configure environment variables
   - Set up networking between the services

3. Once deployment is complete, your application will be available at:
   - Frontend: https://server-monitoring-frontend.azurewebsites.net
   - Backend: https://server-monitoring-backend.azurewebsites.net

For CI/CD setup, see the `azure-deployment-guide.md` file for detailed instructions on setting up GitHub Actions for automated deployments.

### Option 2: Traditional Deployment

### Backend Deployment (Azure App Service)

1. Create an Azure App Service:
   ```bash
   az login
   az group create --name ResourceMonitorGroup --location eastus
   az appservice plan create --name ResourceMonitorPlan --resource-group ResourceMonitorGroup --sku B1 --is-linux
   az webapp create --resource-group ResourceMonitorGroup --plan ResourceMonitorPlan --name your-app-name --runtime "PYTHON|3.8"
   ```

2. Configure environment variables on Azure:
   ```bash
   az webapp config appsettings set --resource-group ResourceMonitorGroup --name your-app-name --settings SSH_HOST=your-server-hostname SSH_USERNAME=your-username SSH_PASSWORD=your-password
   ```
   
   If using SSH key authentication:
   ```bash
   # First, encode your SSH key to base64
   KEY_CONTENT=$(cat /path/to/your/private/key | base64)
   
   # Then set it as an environment variable
   az webapp config appsettings set --resource-group ResourceMonitorGroup --name your-app-name --settings SSH_KEY_CONTENT=$KEY_CONTENT
   ```

3. Deploy your code:
   ```bash
   git archive --format zip --output ./app.zip main
   az webapp deployment source config-zip --resource-group ResourceMonitorGroup --name your-app-name --src ./app.zip
   ```

### Frontend Deployment (Azure Static Web Apps)

1. Create an Azure Static Web App:
   ```bash
   az staticwebapp create --name your-static-app-name --resource-group ResourceMonitorGroup --location eastus --source https://github.com/yourusername/server-resource-monitor --branch main --app-location /frontend --api-location "" --output-location build
   ```

2. Set up environment variables in the frontend:
   - Add a `.env.production` file to the frontend directory:
     ```
     REACT_APP_API_URL=https://your-app-name.azurewebsites.net
     ```
   - OR configure it in Azure Static Web Apps settings.

3. Build and deploy the frontend:
   ```bash
   cd frontend
   npm run build
   ```

### Configuring GitHub Actions for CI/CD

1. In your repository, create a `.github/workflows` directory:
   ```bash
   mkdir -p .github/workflows
   ```

2. Create a workflow file `.github/workflows/azure-deploy.yml`:
   ```yaml
   name: Azure Deploy

   on:
     push:
       branches: [ main ]
     workflow_dispatch:

   jobs:
     build_and_deploy_backend:
       runs-on: ubuntu-latest
       
       steps:
       - uses: actions/checkout@v2
       
       - name: Set up Python
         uses: actions/setup-python@v2
         with:
           python-version: '3.8'
           
       - name: Install dependencies
         run: pip install -r requirements.txt
           
       - name: Deploy to Azure Web App
         uses: azure/webapps-deploy@v2
         with:
           app-name: 'your-app-name'
           publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
           
     build_and_deploy_frontend:
       runs-on: ubuntu-latest
       
       steps:
       - uses: actions/checkout@v2
       
       - name: Set up Node.js
         uses: actions/setup-node@v2
         with:
           node-version: '14'
           
       - name: Install dependencies
         run: |
           cd frontend
           npm install
           
       - name: Build frontend
         run: |
           cd frontend
           echo "REACT_APP_API_URL=https://your-app-name.azurewebsites.net" > .env.production
           npm run build
           
       - name: Deploy to Azure Static Web App
         uses: Azure/static-web-apps-deploy@v1
         with:
           azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
           repo_token: ${{ secrets.GITHUB_TOKEN }}
           action: "upload"
           app_location: "/frontend"
           output_location: "build"
   ```

## Using with Different Servers

To use this application with a different server:

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