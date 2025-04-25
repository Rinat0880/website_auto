import time
from selenium.webdriver.common.by import By

def watch_videos(driver):
    video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw td.state_iconl")

    for block in video_blocks:
        img = block.find_element(By.TAG_NAME, "img")
        src = img.get_attribute("src")

        if "sttop_iconl_yet.gif" in src:

            link = block.find_element(By.XPATH, "../..//a")
            link.click()
            time.sleep(10)
            driver.back()
            time.sleep(3)

            video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw td.state_iconl")
        else:
            print("Уже просмотрено все")
