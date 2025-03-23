# WSL Port Forwarding Script to run WSL IP address like 172.188.0.1:8000 as localhost:8000
# Run as administrator

# Get the primary IP address from WSL
$wslIP = (wsl -- ip -4 addr show eth0 | Select-String -Pattern "inet\s+([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})" | ForEach-Object { $_.Matches.Groups[1].Value }) -split "\s" | Select-Object -First 1

Write-Host "WSL IP address: $wslIP"

# Remove existing port forwarding rules for port 8000 if they exist
Write-Host "Removing existing port forwarding rules for port 8000..."
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0

# Create new port forwarding rule
Write-Host "Creating new port forwarding rule: 0.0.0.0:8000 -> $wslIP`:8000"
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIP

# Display all current port forwarding rules
Write-Host "Current port forwarding rules:"
netsh interface portproxy show v4tov4

# Test the connection
Write-Host "Testing connection to localhost:8000..."
Test-NetConnection -ComputerName localhost -Port 8000

Write-Host "Done. You should now be able to access your WSL services at localhost:8000"