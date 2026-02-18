import requests
import re
import os
import shutil
import sys
import yagmail
import zipfile
import smtplib
import json
from datetime import datetime
from PIL import Image

with open('secrets.json', 'r') as jsonfile:
    data = json.load(jsonfile)

EMAIL = data['email']
PASSWORD = data['password']

PLOT_REGEX = ".*alt=\"\\[IMG\\]\"></td><td><a href=\"(.*?)\">"
PLOTS_URL = "https://covid-nma.com/images/forest/rct/"
DOWNLOADED_FOLDER = "downloaded/"
CACHED_FOLDER = "cached/"
ARCHIVE_FOLDER = "archive/"
HIGHLIGHTED_FOLDER = "highlighted/"
HIGHLIGHTED_ZIP = "highlighted.zip"
ADDED_ZIP = "added.zip"
RECIPIENTS_FILE = "Recipients.txt"

PIXEL_DIFFERENCE_BLOCK_COUNT = 100
PIXEL_DIFFERENCE_THRESHOLD = 30


def create_folders():
    # Create folders
    if not os.path.exists(DOWNLOADED_FOLDER):
        os.mkdir(DOWNLOADED_FOLDER)

    if not os.path.exists(CACHED_FOLDER):
        os.mkdir(CACHED_FOLDER)

    if not os.path.exists(ARCHIVE_FOLDER):
        os.mkdir(ARCHIVE_FOLDER)

    if not os.path.exists(HIGHLIGHTED_FOLDER):
        os.mkdir(HIGHLIGHTED_FOLDER)


def identify_plots() :
    plots = []

    response = requests.get(PLOTS_URL)
    for line in response.text.split("\n"):
        matchObj = re.match(PLOT_REGEX, line)
        if matchObj:
            image = matchObj.group(1)
            plots.append(image)

    return plots


def download_images(plots):
    index = 0
    for imageFile in plots:
        index += 1
        sys.stdout.write("\rDownloading plot %d of %d" % (index, len(plots)))
        sys.stdout.flush()

        with open(DOWNLOADED_FOLDER + imageFile, 'wb') as localFile:
            response = requests.get(PLOTS_URL + imageFile, stream=True)

            if not response.ok:
                print(response)

            for block in response.iter_content(1024):
                if not block:
                    break
                else:
                    localFile.write(block)
    print()


def check_for_updates():
    # Check for new or changed images
    addedImages = []
    updatedImages = []
    for image in os.listdir(DOWNLOADED_FOLDER):
        if not os.path.exists(CACHED_FOLDER + image):
            addedImages.append(image)
        else:
            cachedImageContent = ""
            with open(CACHED_FOLDER + image, 'rb') as archivedImage:
                cachedImageContent = archivedImage.read()

            downloadedImageContent = ""
            with open(DOWNLOADED_FOLDER + image, 'rb') as downloadedImage:
                downloadedImageContent = downloadedImage.read()

            if downloadedImageContent != cachedImageContent:
                updatedImages.append(image)

    return addedImages, updatedImages


def create_highlighted_images_zip(updated_images):
    for img_file in updated_images:
        shutil.copyfile(DOWNLOADED_FOLDER + img_file, HIGHLIGHTED_FOLDER + img_file)

        old_img = Image.open(CACHED_FOLDER + img_file)
        old_pixels = old_img.load()
        new_img = Image.open(HIGHLIGHTED_FOLDER + img_file)
        new_pixels = new_img.load()

        for i in range(PIXEL_DIFFERENCE_BLOCK_COUNT):
            for j in range(PIXEL_DIFFERENCE_BLOCK_COUNT):
                block_updated = False
                x = int(i * new_img.size[0] / PIXEL_DIFFERENCE_BLOCK_COUNT)
                while x < int((i + 1) * new_img.size[0] / PIXEL_DIFFERENCE_BLOCK_COUNT):
                    y = int(j * new_img.size[1] / PIXEL_DIFFERENCE_BLOCK_COUNT)
                    while y < int((j + 1) * new_img.size[1] / PIXEL_DIFFERENCE_BLOCK_COUNT):
                        if x >= old_img.size[0] or y >= old_img.size[1] or sum([abs(new_pixels[x, y][k] - old_pixels[x, y][k]) for k in range(3)]) > PIXEL_DIFFERENCE_THRESHOLD:
                            block_updated = True
                            break
                        y += 1
                    if block_updated:
                        break
                    x += 1

                if not block_updated:
                    for x in range(int(i * new_img.size[0] / PIXEL_DIFFERENCE_BLOCK_COUNT), int((i + 1) * new_img.size[0] / PIXEL_DIFFERENCE_BLOCK_COUNT)):
                        for y in range(int(j * new_img.size[1] / PIXEL_DIFFERENCE_BLOCK_COUNT), int((j + 1) * new_img.size[1] / PIXEL_DIFFERENCE_BLOCK_COUNT)):
                            new_pixels[x, y] = tuple([int(new_pixels[x, y][i] * 3 / 4) for i in range(3)])

                    # for x in range(new_img.size[0]):
                    #     for y in range(new_img.size[1]):
                    #         if x < old_img.size[0] and y < old_img.size[1] and new_pixels[x, y] == old_pixels[x, y]:
                    #             new_pixels[x, y] = tuple([int(new_pixels[x, y][i] / 4) for i in range(3)])

        new_img.save(HIGHLIGHTED_FOLDER + img_file)

    zip_file = zipfile.ZipFile(HIGHLIGHTED_ZIP, "w")
    for filename in os.listdir(HIGHLIGHTED_FOLDER):
        zip_file.write(HIGHLIGHTED_FOLDER + filename)
    zip_file.close()


def create_added_images_zip(addedImages):
    zip_file = zipfile.ZipFile(ADDED_ZIP, "w")
    for filename in addedImages:
        zip_file.write(DOWNLOADED_FOLDER + filename)
    zip_file.close()


def create_attachments(addedImages, updatedImages):
    attachments = []
    if len(updatedImages) > 0:
        create_highlighted_images_zip(updatedImages)
        attachments.append(HIGHLIGHTED_ZIP)

    if len(addedImages) > 0:
        create_added_images_zip(addedImages)
        attachments.append(ADDED_ZIP)

    return attachments


def create_email_contents(addedImages, updatedImages):
    contents = []
    if len(addedImages) > 0:
        message = "%d image%s added" % (len(addedImages), "" if len(addedImages) == 1 else "s")
        contents.append(message)
        print(message)
        for image in addedImages:
            contents.append("- %s" % (PLOTS_URL + image))
        contents.append("")
        contents.append("")

    if len(updatedImages) > 0:
        message = "%d image%s updated" % (len(updatedImages), "" if len(updatedImages) == 1 else "s")
        contents.append(message)
        print(message)
        for image in updatedImages:
            contents.append("- %s" % (PLOTS_URL + image))

    return contents


def send_emails(addedImages, updatedImages, recipients):
    contents = create_email_contents(addedImages, updatedImages)
    attachments = create_attachments(addedImages, updatedImages)

    yag = yagmail.SMTP(EMAIL, PASSWORD)
    for recipient in recipients:
        try:
            yag.send(to=recipient, subject='New Covid Data', contents=contents, attachments=attachments)
        except smtplib.SMTPSenderRefused:
            contents.insert(0, "Too many changed images to attach.")
            contents.insert(1, "")
            contents.insert(2, "")
            yag.send(to=recipient, subject='New Covid Data', contents=contents)


def read_recipients():
    recipients = []
    with open(RECIPIENTS_FILE, "r") as recipientsFile:
        for line in recipientsFile.read().split("\n"):
            if line is not "":
                recipients.append(line)
    return recipients


def archive_new_data():
    # Archive latest download as date of data installed
    zip_file = zipfile.ZipFile(ARCHIVE_FOLDER + datetime.now().strftime("%Y-%m-%d") + ".zip", "w")
    for filename in os.listdir(DOWNLOADED_FOLDER):
        zip_file.write(DOWNLOADED_FOLDER + filename)
    zip_file.close()


if __name__ == "__main__":
    create_folders()
    plots = identify_plots()
    print("%d plots found" % len(plots))

    download_images(plots)
    addedImages, updatedImages = check_for_updates()

    # Send report
    if len(addedImages) == 0 and len(updatedImages) == 0:
        print("No data changes")
    else:
        recipients = read_recipients()
        send_emails(addedImages, updatedImages, recipients)
        archive_new_data()

    # Delete cache
    shutil.rmtree(CACHED_FOLDER)

    # Rename downloaded to cached
    os.rename(DOWNLOADED_FOLDER, CACHED_FOLDER)

    # Delete highlighted
    shutil.rmtree(HIGHLIGHTED_FOLDER)

    # Delete zipped attachments
    if os.path.exists(ADDED_ZIP):
        os.remove(ADDED_ZIP)
    if os.path.exists(HIGHLIGHTED_ZIP):
        os.remove(HIGHLIGHTED_ZIP)
