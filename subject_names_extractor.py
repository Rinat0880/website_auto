from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def extract_subject_names():
    service = Service(executable_path="chromedriver.exe")
    driver = webdriver.Chrome(service=service)

    try:
        driver.get("https://elcampus.otemae.ac.jp/")
        _ = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.NAME, "login_id"))

        )
        input_element = driver.find_element(By.NAME, "login_id")
        input_element.clear()
        input_element.send_keys("z221241w")

        input_element = driver.find_element(By.NAME, "login_pw")
        input_element.clear()
        input_element.send_keys("N9ds4XCe")

        button = driver.find_element(By.ID, "msg_btn_login")
        button.click()

        _ = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "subject_list"))
        )

        subject_elements = driver.find_elements(By.CSS_SELECTOR, ".subject_list_hdr h4 a")

        # Extract the text from each element into an array
        subject_names = [element.text for element in subject_elements]

        return subject_names
    finally:
        driver.quit()

if __name__ == "__main__":
    subject_names = extract_subject_names()
    print(subject_names)

