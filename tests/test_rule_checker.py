import unittest

from src.rule_checker import check_case


class RuleCheckerTests(unittest.TestCase):
    def test_flags_duplicate_ip_and_gateway_mismatch(self):
        case = {
            "assigned_ips": "10.0.0.10|10.0.0.10",
            "subnet_masks": "PC1=255.255.255.0",
            "expected_mask": "255.255.255.0",
            "default_gateway": "10.0.0.1",
            "gateway_interface_ip": "10.0.0.254",
            "interface_status": "g0/1:up",
            "required_vlans": "10",
            "configured_vlans": "10",
            "required_routes": "",
            "configured_routes": "",
        }
        rules = {f["rule"] for f in check_case(case)}
        self.assertIn("duplicate_ip", rules)
        self.assertIn("gateway_mismatch", rules)

    def test_flags_missing_vlan_route_and_interface_down(self):
        case = {
            "assigned_ips": "",
            "subnet_masks": "",
            "expected_mask": "",
            "default_gateway": "",
            "gateway_interface_ip": "",
            "interface_status": "g0/0:down|g0/1:up",
            "required_vlans": "20|30",
            "configured_vlans": "20",
            "required_routes": "10.10.10.0/24|10.20.20.0/24",
            "configured_routes": "10.10.10.0/24",
        }
        rules = {f["rule"] for f in check_case(case)}
        self.assertIn("interface_down", rules)
        self.assertIn("missing_vlan", rules)
        self.assertIn("missing_route", rules)


if __name__ == "__main__":
    unittest.main()
