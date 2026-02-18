import os
import shutil
import sys

RECIPIENTS_FILE = "Recipients.txt"

def read_recipients():
    recipients = []
    with open(RECIPIENTS_FILE, "r") as recipientsFile:
        for line in recipientsFile.read().split("\n"):
            if line is not "":
                recipients.append(line)
    return recipients


if __name__ == "__main__":
    recipients = read_recipients()
    for recipient in recipients:
        print(recipient)
        recipient
