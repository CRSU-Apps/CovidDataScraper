import imaplib
import re
import yagmail
import json

with open('secrets.json', 'r') as jsonfile:
    data = json.load(jsonfile)

EMAIL = data['email']
PASSWORD = data['password']

SENDER_REGEX = "From: .* <(.*)>"
SUBJECT_REGEX = "Subject: (.*)"
SUBSCRIBE = "subscribe"
UNSUBSCRIBE = "unsubscribe"
RECIPIENTS_FILE = "Recipients.txt"
SUBSCRIBER_CONFIRMATION = "Thank you for subscribing for new data notifications. You can unsubscribe at any time by emailing this address with the subject line \"Unsubscribe\" in a new email chain."
UNSUBSCRIBER_CONFIRMATION = "You have successfully unsubscribed from new data notifications. You can resubscribe at any time by emailing this address with the subject line \"Subscribe\" in a new email chain."

# Make SSL connnection with gmail
connection = imaplib.IMAP4_SSL('imap.gmail.com')

# Login
connection.login(EMAIL, PASSWORD)

# Check for incoming mail
connection.select('Inbox')

# Fetch unread email indices
messageIndices = connection.search(None, '(UNSEEN)')[1][0].split()


subscribe_requests = []
unsubscribe_requests = []


for index in messageIndices:
    sender = None
    subject = None

    data = connection.fetch(index, '(RFC822)')[1][0][1].decode("utf-8").split("\r\n")
    bodyStarted = False
    for line in data:
        # Find sender
        matchObj = re.match(SENDER_REGEX, line)
        if matchObj:
            sender = matchObj.group(1)

        # Find subject
        matchObj = re.match(SUBJECT_REGEX, line)
        if matchObj:
            subject = matchObj.group(1)

    if subject.lower().replace(" ", "") == SUBSCRIBE:
        subscribe_requests.append(sender)
    elif subject.lower().replace(" ", "") == UNSUBSCRIBE:
        unsubscribe_requests.append(sender)

connection.close()

if len(subscribe_requests) != 0 or len(unsubscribe_requests) != 0:
    # Read recipients
    recipients = []
    with open(RECIPIENTS_FILE, "r") as recipientsFile:
        for line in recipientsFile.read().split("\n"):
            if line is not "":
                recipients.append(line)

    for subscriber in subscribe_requests:
        if subscriber not in recipients:
            print("Subscriber added: %s" % subscriber)
            recipients.append(subscriber)
            # Send confirmation email
            yag = yagmail.SMTP(EMAIL, PASSWORD)
            yag.send(to=subscriber, subject='Subscription Confirmation', contents=SUBSCRIBER_CONFIRMATION)

    for unsubscriber in unsubscribe_requests:
        print("Subscriber removed: %s" % unsubscriber)
        recipients.remove(unsubscriber)
        # Send confirmation email
        yag = yagmail.SMTP(EMAIL, PASSWORD)
        yag.send(to=unsubscriber, subject='Unsubscription Confirmation', contents=UNSUBSCRIBER_CONFIRMATION)

    with open(RECIPIENTS_FILE, "w") as recipientsFile:
        for recipient in recipients:
            recipientsFile.write("%s\n" % recipient)
