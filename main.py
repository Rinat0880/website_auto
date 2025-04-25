import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

#-------- Логин и пароль в config.py редактяться

from config import login, password, subject_name

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

time.sleep(5)

wait = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CLASS_NAME, "lesson_name"))
)
lesson_blocks = driver.find_elements(By.CLASS_NAME, "lesson_name")

for i in range(1, 16):
    lesson_number = f"第{i}回"
    for block in lesson_blocks:
        if lesson_number in block.text:
            print(f"Нажимаем на блок урока: {lesson_number}")
            try:
                block.click()
                time.sleep(1)
            except Exception as e:
                print(f"Не удалось нажать на блок {lesson_number}: {str(e)}")
            break
    else:
        print(f"Блок урока {lesson_number} не найден")

time.sleep(1)


wait = WebDriverWait(driver, 5).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bw td.state_iconl"))

)

original_window = driver.current_window_handle

videos_watched = 0
i = 0
while True:  
    try:
        wait = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bw td.state_iconl"))
        )
        video_blocks = driver.find_elements(By.CSS_SELECTOR, "div.type_bw")
        
        found_unwatched = False
        for block in video_blocks:
            try:
                icon_cell = block.find_element(By.CSS_SELECTOR, "td.state_iconl img")
                src = icon_cell.get_attribute("src")
                
                if "sttop_iconl_yet.gif" in src:
                    found_unwatched = True
                    i += 1
                    time.sleep(1)
                    try:
                        contents_name_cell = block.find_element(By.CSS_SELECTOR, "td.contents_name a")
                        print(f"Открываем видео {i}: {contents_name_cell.text}")
                        contents_name_cell.click()
                        videos_watched += 1

                        time.sleep(10)
                        
                        for window_handle in driver.window_handles:
                            if window_handle != original_window:
                                video_window = window_handle
                                driver.switch_to.window(video_window)
                                print(f"Переключились на нужный экран")
                                break
                        print(f"Ждем 10 секунд для засчитывания просмотра видео {i}...")
                        time.sleep(3)
                        
                        driver.close()
                        
                        driver.switch_to.window(original_window)
                        print(f"Успешно просмотрено видео {i}")
                        
                        time.sleep(10)
                        
                        break
                        
                    except Exception as e:
                        print(f"Ошибка при просмотре видео {i}: {e}")
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
                        time.sleep(2)
            except Exception as e:
                print(f"Не удалось проверить статус видео: {e}")
                continue
        
        if not found_unwatched:
            print("Больше нет непросмотренных видео")
            break
            
    except Exception as e:
        print(f"Ошибка при поиске видео: {e}")
        time.sleep(5)

print(f"Завершено! Просмотрено {videos_watched} новых видео")


time.sleep(10)
driver.quit()