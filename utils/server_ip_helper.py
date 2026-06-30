"""Utility module to retrieve server IP from the utils/server_ip file."""

import os


def get_server_ip():
    """
    Read server IP from utils/server_ip file.
    If file doesn't exist, prompt user for server IP and save it.
    """
    # Get the utils directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_ip_file = os.path.join(current_dir, "server_ip")

    # Check if file exists
    if os.path.exists(server_ip_file):
        with open(server_ip_file, "r") as f:
            server_ip = f.read().strip()
            if server_ip:
                return server_ip

    # File doesn't exist or is empty, prompt user
    server_ip = input("Enter server IP: ").strip()

    # Save to file
    with open(server_ip_file, "w") as f:
        f.write(server_ip)

    return server_ip
