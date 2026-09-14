#!/usr/bin/env python
# Pre-install validation script for MPB management packs.
# Checks that the VCF Operations environment variable is set before install.

import sys
import os


def exitValidateScript(exitDescription, exitCode=0):
    print("Exiting-{0}, exit code: {1}".format(exitDescription, str(exitCode)))
    sys.exit(exitCode)


print("Entering validate management pack")
print("Checking if VCOPS_BASE is set")
try:
    os.environ["VCOPS_BASE"]
except KeyError:
    exitValidateScript("Failed-VCOPS_BASE check failed", 1)
print("VCOPS_BASE check passed")
print("Exiting validate management pack")
sys.exit()
