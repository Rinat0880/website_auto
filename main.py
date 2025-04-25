import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from watcher import watch_videos

#-------- logini i paroli zdes edit

try:
    from config import login, password, subject_name
except ImportError:
    print("Config file not found. Please create a config.py file based on config.example.py")
    print("See README.md for instructions")
    exit(1)

#--------
service = Service(executable_path="chromedriver.exe")
driver = webdriver.Chrome(service=service)

driver.get("https://elcampus.otemae.ac.jp/")

wait = WebDriverWait(driver, 5).until(
    EC.presence_of_element_located((By.NAME, "login_id"))

)
input_element = driver.find_element(By.NAME, "login_id")
input_element.clear()
input_element.send_keys(login)

input_element = driver.find_element(By.NAME, "login_pw")
input_element.clear()
input_element.send_keys(password)

button = driver.find_element(By.ID, "msg_btn_login")
button.click()

portal_div = WebDriverWait(driver, 5).until(
    EC.presence_of_element_located((By.CLASS_NAME, "subject_list"))
)

lesson_link = portal_div.find_element(By.LINK_TEXT, subject_name)
lesson_link.click()

wait = WebDriverWait(driver, 5).until(
    EC.presence_of_element_located((By.LINK_TEXT, "授業"))

)
link = driver.find_element(By.LINK_TEXT, "授業")
link.click()


wait = WebDriverWait(driver, 5).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bw td.state_iconl"))

)

wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bw")))
video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw")


videos_watched = 0
for i, block in enumerate(video_blocks):
        try:
            try:
                icon_cell = block.find_element(By.CSS_SELECTOR, "td.state_iconl img")
                src = icon_cell.get_attribute("src")
                
                if "sttop_iconl_yet.gif" in src:
                    contents_name_cell = block.find_element(By.CSS_SELECTOR, "td.contents_name a")
                    print(f"Watching video {i+1}: {contents_name_cell.text}")
                    contents_name_cell.click()
                    videos_watched += 1
                        
                    time.sleep(15) 
                       
                    driver.back()
                    time.sleep(5) 
                        
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bw td.state_iconl")))
                    video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw td.state_iconl")
            except NoSuchElementException as e:
                    print(f"Could not find clickable link for video {i+1}: {e}")
                    continue
            else:
                print(f"Video {i+1} already watched")
        except Exception as e:
            print(f"Error processing video block {i+1}: {e}")
            continue
    
print(f"Finished watching {videos_watched} new videos")



# video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw td.state_iconl")

# for block in video_blocks:
#     img = block.find_element(By.TAG_NAME, "img")
#     src = img.get_attribute("src")
#     if "sttop_iconl_yet.gif" in src:
#         link = block.find_element(By.CLASS_NAME, "contents_name")
#         link.click()
#         time.sleep(10)
#         driver.back()
#         time.sleep(3)

#         video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw td.state_iconl")
#     else:
#         print("Уже просмотрено все")

time.sleep(10)
driver.quit()