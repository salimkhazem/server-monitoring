import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Box,
  Card,
  CardContent,
  LinearProgress,
  List,
  ListItem,
  ListItemText,
  CircularProgress,
  Divider,
  ThemeProvider,
  createTheme,
  CssBaseline,
  AppBar,
  Toolbar,
  useMediaQuery,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Memory as MemoryIcon,
  Storage as StorageIcon,
  Speed as SpeedIcon,
  Person as PersonIcon,
  Refresh as RefreshIcon,
  DeveloperBoard as GpuIcon,
} from '@mui/icons-material';
import axios from 'axios';

// Get the API URL from environment variables or use default
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function App() {
  const [gpuData, setGpuData] = useState({ gpus: [], active_users: [], system_resources: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)');

  const theme = createTheme({
    palette: {
      mode: 'dark',
      primary: {
        main: '#3f51b5',
      },
      secondary: {
        main: '#f50057',
      },
      background: {
        default: '#121212',
        paper: '#1e1e1e',
      },
    },
    components: {
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            boxShadow: '0 8px 16px 0 rgba(0,0,0,0.2)',
            transition: 'transform 0.3s ease-in-out',
            '&:hover': {
              transform: 'translateY(-5px)',
            },
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: {
            borderRadius: 12,
          },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: {
            borderRadius: 5,
            height: 10,
          },
        },
      },
    },
  });

  const getProgressColor = (value) => {
    if (value < 50) return '#4caf50'; // green
    if (value < 80) return '#ff9800'; // orange
    return '#f44336'; // red
  };

  const fetchData = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/gpu-status`);
      setGpuData(response.data);
      setLastUpdated(new Date());
      setError(null);
    } catch (err) {
      setError('Failed to fetch GPU data. Please check if the backend server is running.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    setLoading(true);
    fetchData();
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
          <CircularProgress size={60} />
        </Box>
      </ThemeProvider>
    );
  }

  if (error) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh" flexDirection="column">
          <Typography color="error" variant="h5" gutterBottom>{error}</Typography>
          <IconButton color="primary" onClick={handleRefresh} sx={{ mt: 2 }}>
            <RefreshIcon />
          </IconButton>
        </Box>
      </ThemeProvider>
    );
  }

  const { gpus, active_users, system_resources } = gpuData;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{
        background: 'linear-gradient(135deg, #121212 0%, #2d2d2d 100%)',
        minHeight: '100vh',
        pb: 4
      }}>
        <AppBar position="static" sx={{ mb: 4, background: 'linear-gradient(90deg, #3f51b5 0%, #9c27b0 100%)' }}>
          <Toolbar>
            <GpuIcon sx={{ mr: 2 }} />
            <Typography variant="h5" component="h1" sx={{ flexGrow: 1, fontWeight: 600 }}>
              Server Resource Monitor
            </Typography>
            <Tooltip title="Refresh data">
              <IconButton color="inherit" onClick={handleRefresh}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>

        <Container maxWidth="lg">
          <Box sx={{ mb: 1, display: 'flex', justifyContent: 'flex-end' }}>
            <Typography variant="caption" color="text.secondary">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </Typography>
          </Box>

          {/* System Resources Section */}
          <Paper 
            sx={{ 
              p: 3, 
              mb: 3, 
              background: 'linear-gradient(135deg, rgba(66,66,66,0.4) 0%, rgba(33,33,33,0.4) 100%)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,255,255,0.1)'
            }}
            elevation={4}
          >
            <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
              System Resources
            </Typography>
            <Grid container spacing={3}>
              {/* CPU Card */}
              <Grid item xs={12} md={4}>
                <Card sx={{ height: '100%' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <SpeedIcon sx={{ mr: 1, color: '#f44336' }} />
                      <Typography variant="h6">
                        CPU Usage
                      </Typography>
                    </Box>
                    <Box sx={{ position: 'relative', mb: 2 }}>
                      <CircularProgress
                        variant="determinate"
                        value={system_resources.cpu?.usage_percent || 0}
                        size={100}
                        thickness={6}
                        sx={{ 
                          color: getProgressColor(system_resources.cpu?.usage_percent || 0),
                          display: 'block',
                          mx: 'auto'
                        }}
                      />
                      <Box
                        sx={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          bottom: 0,
                          right: 0,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Typography variant="h5" component="div">
                          {system_resources.cpu?.usage_percent?.toFixed(1) || 0}%
                        </Typography>
                      </Box>
                    </Box>
                    <Typography variant="body2" sx={{ textAlign: 'center' }} color="text.secondary">
                      {system_resources.cpu?.cores || 'N/A'} cores
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* Memory Card */}
              <Grid item xs={12} md={4}>
                <Card sx={{ height: '100%' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <MemoryIcon sx={{ mr: 1, color: '#3f51b5' }} />
                      <Typography variant="h6">
                        Memory Usage
                      </Typography>
                    </Box>
                    <Box sx={{ position: 'relative', mb: 2 }}>
                      <CircularProgress
                        variant="determinate"
                        value={system_resources.memory?.usage_percent || 0}
                        size={100}
                        thickness={6}
                        sx={{ 
                          color: getProgressColor(system_resources.memory?.usage_percent || 0),
                          display: 'block',
                          mx: 'auto'
                        }}
                      />
                      <Box
                        sx={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          bottom: 0,
                          right: 0,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Typography variant="h5" component="div">
                          {system_resources.memory?.usage_percent?.toFixed(1) || 0}%
                        </Typography>
                      </Box>
                    </Box>
                    <Typography variant="body2" sx={{ textAlign: 'center' }} color="text.secondary">
                      {system_resources.memory?.used || 0}MB / {system_resources.memory?.total || 0}MB
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              {/* Disk Card */}
              <Grid item xs={12} md={4}>
                <Card sx={{ height: '100%' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <StorageIcon sx={{ mr: 1, color: '#9c27b0' }} />
                      <Typography variant="h6">
                        Disk Usage
                      </Typography>
                    </Box>
                    <Box sx={{ position: 'relative', mb: 2 }}>
                      <CircularProgress
                        variant="determinate"
                        value={system_resources.disk?.usage_percent || 0}
                        size={100}
                        thickness={6}
                        sx={{ 
                          color: getProgressColor(system_resources.disk?.usage_percent || 0),
                          display: 'block',
                          mx: 'auto'
                        }}
                      />
                      <Box
                        sx={{
                          position: 'absolute',
                          top: 0,
                          left: 0,
                          bottom: 0,
                          right: 0,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <Typography variant="h5" component="div">
                          {system_resources.disk?.usage_percent || 0}%
                        </Typography>
                      </Box>
                    </Box>
                    <Typography variant="body2" sx={{ textAlign: 'center' }} color="text.secondary">
                      {system_resources.disk?.used || 'N/A'} / {system_resources.disk?.total || 'N/A'}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Paper>

          {/* GPU Section */}
          <Paper 
            sx={{ 
              p: 3, 
              mb: 3, 
              background: 'linear-gradient(135deg, rgba(66,66,66,0.4) 0%, rgba(33,33,33,0.4) 100%)',
              backdropFilter: 'blur(10px)',
              border: '1px solid rgba(255,255,255,0.1)'
            }}
            elevation={4}
          >
            <Typography variant="h5" gutterBottom sx={{ mb: 3 }}>
              GPU Resources
            </Typography>
            <Grid container spacing={3}>
              {/* GPU Cards */}
              {gpus.map((gpu) => (
                <Grid item xs={12} md={6} key={gpu.id}>
                  <Card sx={{ 
                    background: 'linear-gradient(135deg, #2d2d2d 0%, #1a1a1a 100%)',
                    border: '1px solid rgba(255,255,255,0.05)',
                  }}>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                        <GpuIcon sx={{ mr: 1, color: '#4caf50' }} />
                        <Typography variant="h6">
                          GPU {gpu.id}: {gpu.name}
                        </Typography>
                      </Box>
                      
                      <Box sx={{ mb: 4 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Memory Usage
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {gpu.memory_used}MB / {gpu.memory_total}MB
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={(gpu.memory_used / gpu.memory_total) * 100}
                          sx={{ 
                            height: 12, 
                            borderRadius: 6,
                            backgroundColor: 'rgba(255,255,255,0.1)',
                            '& .MuiLinearProgress-bar': {
                              background: `linear-gradient(90deg, ${getProgressColor((gpu.memory_used / gpu.memory_total) * 100)} 0%, #76ff03 100%)`,
                              borderRadius: 6,
                            }
                          }}
                        />
                      </Box>

                      <Grid container spacing={2} sx={{ mb: 2 }}>
                        <Grid item xs={6}>
                          <Card sx={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                            <CardContent>
                              <Typography variant="body2" color="text.secondary" gutterBottom>
                                Temperature
                              </Typography>
                              <Typography variant="h6" sx={{ 
                                color: getProgressColor(parseInt(gpu.temperature) * 1.1),
                                fontWeight: 'bold'
                              }}>
                                {gpu.temperature}°C
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                        <Grid item xs={6}>
                          <Card sx={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                            <CardContent>
                              <Typography variant="body2" color="text.secondary" gutterBottom>
                                Power Usage
                              </Typography>
                              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                {gpu.power_usage}W
                              </Typography>
                            </CardContent>
                          </Card>
                        </Grid>
                      </Grid>

                      <Card sx={{ backgroundColor: 'rgba(255,255,255,0.05)' }}>
                        <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                          <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <PersonIcon sx={{ mr: 1, fontSize: 18, color: 'text.secondary' }} />
                            <Typography variant="body2" color="text.secondary" component="span">
                              User:
                            </Typography>
                            <Typography variant="body2" sx={{ ml: 1 }}>
                              {gpu.user || 'No user'}
                            </Typography>
                          </Box>
                        </CardContent>
                      </Card>
                    </CardContent>
                  </Card>
                </Grid>
              ))}

              {/* Active Users */}
              <Grid item xs={12}>
                <Card sx={{ backgroundColor: 'rgba(33,33,33,0.7)' }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <PersonIcon sx={{ mr: 1, color: '#ff9800' }} />
                      <Typography variant="h6">
                        Active Users
                      </Typography>
                    </Box>
                    {active_users.length > 0 && active_users[0] !== '' ? (
                      <List>
                        {active_users.map((user, index) => (
                          <ListItem 
                            key={index}
                            sx={{ 
                              mb: 1, 
                              backgroundColor: 'rgba(255,255,255,0.05)',
                              borderRadius: 2
                            }}
                          >
                            <PersonIcon sx={{ mr: 2, color: '#ff9800' }} />
                            <ListItemText primary={user} />
                          </ListItem>
                        ))}
                      </List>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        No active users at the moment
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          </Paper>
        </Container>
      </Box>
    </ThemeProvider>
  );
}

export default App; 