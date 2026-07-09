#!/usr/bin/env python
# Post-install script for MPB management packs.
#
# Adapted from reference MPB-generated paks (GitHub-1.0.0.2.pak,
# Broadcom Security Advisories-1.0.1.6.pak). The describe.xml bundled in
# conf/ is read by the VCF Ops adapter loader at startup — no runtime
# generation is required. This script triggers a redescribe and imports
# any bundled content (views, reports, supermetrics, dashboards).
#
# Template variables replaced by builder.py at pak assembly time:
#   ADAPTER_KIND_PLACEHOLDER   — replaced with the adapter kind key
#   ADAPTER_DIR_PLACEHOLDER    — replaced with the adapter directory name

import datetime
import os
import os.path
import sys
import shutil
import subprocess
import time
import platform
import pwd
import grp

from shutil import copyfile


class Directory:
    def __init__(self, path):
        self.path = path

    def is_directory(self):
        return os.path.isdir(self.path)

    def get_files(self):
        return os.listdir(self.path)

    def get_files_of_type(self, *types):
        files = []
        for f in os.listdir(self.path):
            for t in types:
                if f.endswith(t):
                    files.append(f)
                    break
        return files


class File:
    def __init__(self, filename):
        self.filename = filename

    def append_line(self, text):
        self.append(text + "\n")

    def append(self, text):
        with open(self.filename, "a") as fh:
            fh.write(text)

    def write(self, text):
        with open(self.filename, "w") as fh:
            fh.write(text)

    def read(self):
        with open(self.filename, "r") as fh:
            return fh.read()

    def copy_to(self, destination):
        copyfile(self.filename, r"" + destination)


# Read environment variables
vcops_base = os.environ["VCOPS_BASE"]

# Set up paths
adapter_kind_key = "{adapter_kind}"
adapter_dir_name = "{adapter_dir}"
adapter_base = vcops_base + "/user/plugins/inbound/" + adapter_dir_name + "/"

# Ensure work dir exists
work_path = os.path.join(adapter_base, "work")
if not os.path.exists(work_path):
    file_mode = 0o555
    try:
        uid = pwd.getpwnam("admin").pw_uid
        gid = grp.getgrnam("admin").gr_gid
        os.mkdir(work_path, file_mode)
        os.chown(work_path, uid, gid)
    except KeyError as err:
        sys.stderr.write("Error creating work dir {0}".format(err))
        sys.exit(-1)

log_file = File(adapter_base + "/work/install.log")
last_build_version_file = File(vcops_base + "/user/conf/lastbuildversion.txt")
legacy_ops_cli_directory = Directory(vcops_base + "/tools/vcopscli/")
ops_cli_directory = Directory(vcops_base + "/tools/opscli/")

views_directory = Directory(adapter_base + "/conf/views/")
reports_directory = Directory(adapter_base + "/conf/reports/")
supermetrics_directory = Directory(adapter_base + "/conf/supermetrics/")
dashboard_directory = Directory(adapter_base + "/conf/dashboards/")

if ops_cli_directory.is_directory():
    ops_cli = "ops-cli.py"
else:
    ops_cli_directory = legacy_ops_cli_directory
    ops_cli = "vcops-cli.py"

# Get version info
version = last_build_version_file.read().split()[4].split(".")
version_major = int(version[0])
version_minor = int(version[1])
version_point = int(version[2])

log_file.append_line("Python post install script started")
log_file.append_line(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
log_file.append_line(
    "VCF Operations Version: "
    + str(version_major) + "." + str(version_minor) + "." + str(version_point)
)
log_file.append_line("")

original_directory = os.path.dirname(os.path.abspath(__file__))
os.chdir(ops_cli_directory.path)

# Trigger redescribe so VCF Ops picks up the describe.xml from conf/
log_file.append_line("Initiating redescribe...")
subprocess.call([sys.executable, ops_cli, "control", "redescribe", "--force"])
time.sleep(30)

# Import views
log_file.append_line("Importing views...")
if views_directory.is_directory():
    for f in views_directory.get_files():
        view_file = views_directory.path + f
        log_file.append_line("Processing view file: " + view_file)
        subprocess.call([sys.executable, ops_cli, "view", "import", view_file, "--force"])
log_file.append_line("Finished adding views.")

# Import reports
log_file.append_line("Importing reports...")
if reports_directory.is_directory():
    for f in reports_directory.get_files():
        report_file = reports_directory.path + f
        log_file.append_line("Processing report file: " + report_file)
        subprocess.call(
            [sys.executable, ops_cli, "report", "import", report_file, "--force"]
        )
log_file.append_line("Finished adding reports.")

# Import supermetrics
log_file.append_line("Importing supermetrics...")
if supermetrics_directory.is_directory():
    for subdirectory in next(os.walk(supermetrics_directory.path))[1]:
        supermetrics_subdirectory = Directory(
            supermetrics_directory.path + subdirectory + "/"
        )
        log_file.append_line(
            "Processing SuperMetrics for ResourceKind " + subdirectory
        )
        super_files = supermetrics_subdirectory.get_files_of_type(".xml", ".json")
        for super_file in super_files:
            supermetric_file = supermetrics_subdirectory.path + super_file
            log_file.append_line("Processing " + supermetric_file + " file.")
            subprocess.call(
                [
                    sys.executable, ops_cli, "supermetric", "import",
                    supermetric_file,
                    "--packages",
                    adapter_kind_key + "-" + subdirectory + "-Supermetrics",
                    "--check", "true",
                ]
            )
        subprocess.call(
            [
                sys.executable, ops_cli, "objtype", "configure",
                adapter_kind_key + ":" + subdirectory,
                "--smpackage",
                adapter_kind_key + "-" + subdirectory + "-Supermetrics",
            ]
        )
log_file.append_line("Finished adding supermetrics.")

# Import dashboards
log_file.append_line("Installing dashboards...")
if dashboard_directory.is_directory():
    for f in dashboard_directory.get_files_of_type(".json"):
        dashboard_file = dashboard_directory.path + f
        log_file.append_line("Processing dashboard file: " + dashboard_file)
        subprocess.call(
            [
                sys.executable, ops_cli, "dashboard", "import",
                "admin", dashboard_file, "--share", "all", "--force",
            ]
        )
log_file.append_line("Finished adding dashboards.")

log_file.append_line("Finished content import.")

os.chdir(original_directory)
