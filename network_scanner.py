"""
Network Interface Scanner for Windows
Detects active physical network adapters (Wi-Fi, USB Tethering / RNDIS, Ethernet)
and validates their local IP addresses for socket binding.
"""

import socket
from typing import List, Dict, Any

try:
    import psutil
except ImportError:
    psutil = None


def test_interface_connectivity(ip: str, test_host: str = "1.1.1.1", test_port: int = 53, timeout: float = 2.0) -> bool:
    """
    Tests whether a socket bound to a specific local interface IP can reach the internet.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        # Force the socket to exit through this specific local IP
        sock.bind((ip, 0))
        sock.connect((test_host, test_port))
        sock.close()
        return True
    except Exception:
        return False


def get_active_interfaces(test_internet: bool = True) -> List[Dict[str, Any]]:
    """
    Returns a list of active network interfaces suitable for channel bonding.
    Each item contains:
      - name: Adapter display name
      - ip: Local IPv4 address
      - is_up: Operational status
      - online: Whether outgoing traffic through this IP reaches the internet
    """
    if psutil is None:
        raise RuntimeError("The 'psutil' package is required. Run 'pip install psutil'.")

    adapters = []
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    # Common virtualization or internal interface keywords to skip
    excluded_keywords = [
        "loopback", "vethernet", "vmware", "virtualbox",
        "hyper-v", "wsl", "docker", "bluetooth", "npcap"
    ]

    for iface_name, iface_stat in stats.items():
        # Skip down adapters
        if not iface_stat.isup:
            continue

        lower_name = iface_name.lower()
        if any(keyword in lower_name for keyword in excluded_keywords):
            continue

        interface_addrs = addrs.get(iface_name, [])
        for addr in interface_addrs:
            # We only bind IPv4 addresses
            if addr.family == socket.AF_INET:
                ip = addr.address
                # Skip localhost / autoconfiguration APIPA (169.254.x.x)
                if ip.startswith("127.") or ip.startswith("169.254."):
                    continue

                online = test_interface_connectivity(ip) if test_internet else True
                
                # Tag adapter type hint for easy identification
                adapter_type = "Wi-Fi" if "wi-fi" in lower_name or "wireless" in lower_name else (
                    "USB Tethering" if any(k in lower_name for k in ["rndis", "tether", "cellular", "remote ndis"]) else "Ethernet / Network"
                )

                adapters.append({
                    "name": iface_name,
                    "ip": ip,
                    "netmask": addr.netmask,
                    "speed_mbps": iface_stat.speed,
                    "type": adapter_type,
                    "online": online
                })

    return adapters


if __name__ == "__main__":
    print("Scanning active network interfaces...")
    interfaces = get_active_interfaces()
    if not interfaces:
        print("No active network adapters found.")
    else:
        for idx, iface in enumerate(interfaces, 1):
            status = "Online (Internet OK)" if iface["online"] else "Offline / No Route"
            print(f"[{idx}] {iface['name']} ({iface['type']})")
            print(f"    IP: {iface['ip']} | Status: {status}")
