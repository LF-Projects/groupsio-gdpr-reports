# Generate reports about Groups.io activity for GDPR requests

This utility is to be used when responding to a GDPR request.  It scans any Groups.io instances for which the user is a moderator or admin, and generates a report of any activity related to the requestor.

Prerequisites:
 * An admin-level account on any Groups.io groups you need to scan (with password set)
 * Python 3 with pre-reqs installed: `pip3 install fpdf html requests`

## How to use it

Run `python3 groupsio-gdpr-report.py` from your terminal.

## Contact info

If you have an issue and it is not security-related, please open an issue at [https://github.com/brianwarner/mgroupsio-gdpr-report](https://github.com/brianwarner/groupsio-gdpr-reports).  If it is security-related, please contact me directly at <bwarner@linuxfoundation.org>.

---

**Brian Warner** | [The Linux Foundation](https://linuxfoundation.org) | <bwarner@linuxfoundation.org>, <brian@bdwarner.com> | [@realBrianWarner](https://twitter.com/realBrianWarner)

