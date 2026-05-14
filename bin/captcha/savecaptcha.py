import json
import os
import pandas as pd
import subprocess
import sys
import re
from openpyxl import load_workbook
import time
# import tempfile
import shutil
# import logging
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from selenium import webdriver
import chromedriver_autoinstaller
from selenium.webdriver.chrome.options import Options
import shutil
import urllib.request
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from urllib.parse import urlparse
import requests
from selenium.common.exceptions import NoAlertPresentException

import base64
import io
from PIL import Image



from captcha_solver import predict_captcha




mobile_no = "7059141414"

# Install chromedriver if it doesn't exist
chromedriver_autoinstaller.install()

# Set up Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--disable-application-cache")  # Disable application cache
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu") # Disable GPU hardware acceleration (if needed)
chrome_options.add_argument("--log-level=3")

# Create a webdriver instance with headless option
driver = webdriver.Chrome(options=chrome_options)

# Open the URL three times with a 5-second interval
for _ in range(6):
    try:
        driver.get("https://www.ireps.gov.in/epsn/guestLogin.do")
        break
    except Exception as e:
        print("https://www.ireps.gov.in/epsn/guestLogin.do - Exception")

    time.sleep(6)
    print("Retrying...")




def get_verification(driver):
    captcha_chars = None


    # Step 1: Get captcha image element
    img_element = driver.find_element(By.ID, "imgCaptcha")
    src = img_element.get_attribute("src")

    # Save captcha image to temp.png
    if src.startswith("data:image"):  # If base64 encoded
        header, encoded = src.split(",", 1)
        data = base64.b64decode(encoded)
        with open("temp.png", "wb") as f:
            f.write(data)
    else:  # If src is a URL
        response = requests.get(src)
        with open("temp.png", "wb") as f:
            f.write(response.content)

    # Step 2: Run prediction
    test_image = "temp.png"
    predicted_text = predict_captcha("captcha_model.pth", test_image)
    print(f"Predicted text: {predicted_text}")

    # Step 3: Remove temp.png
    if os.path.exists("temp.png"):
        os.remove("temp.png")

    captcha_chars = predicted_text.strip()


    return driver, captcha_chars









# generate OTP
def generate_otp(driver, mobile_no):
    driver.refresh()
    time.sleep(3)
    
    # print("Current Mobile No. :", mobile_no)
    driver, Verification_code = get_verification(driver)
    # mobile_no = input("Enter 10 digit Mobile No: ")
    driver.execute_script("document.getElementById('mobileNo').value='" + mobile_no + "'")

    driver.execute_script("document.getElementById('verification').value='" + Verification_code + "'")
    

    driver.find_element("xpath", "//input[@value='Get OTP']").click()
    time.sleep(3)

    try:
        # Check if an alert is present
        alert = driver.switch_to.alert
        print("Alert Text:", alert.text)
        if alert.text == "you have entered wrong verification code.":
            alert.accept()
            generate_otp(driver, mobile_no)
        else: #if alert.text == "you have entered wrong verification code.":
            alert.accept()
    except NoAlertPresentException:
        print("No alert present after clicking 'Get OTP'")
    return driver




driver = generate_otp(driver, mobile_no)