import time
import logging
from contextlib import contextmanager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    TimeoutException, 
    WebDriverException
)

LOG_LEVEL = logging.INFO  

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

try:
    from config import login, password, subject_names
except ImportError:
    logger.error("Не удалось импортировать config.py. Проверьте наличие файла.")
    exit(1)

class VideoAutomation:
    def __init__(self, chromedriver_path="chromedriver.exe"):
        self.chromedriver_path = chromedriver_path
        self.driver = None
        self.wait_timeout = 15
        self.video_open_delay = 10
        self.video_close_delay = 10
        
    def setup_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-translate")

            service = Service(executable_path=self.chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            logger.info("Драйвер успешно инициализирован")
            return True
        except Exception as e:
            logger.error(f"Ошибка при инициализации драйвера: {e}")
            return False
    
    def login(self):
        try:
            self.driver.get("https://elcampus.otemae.ac.jp/")
            
            # Ожидание поля логина
            login_field = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.NAME, "login_id"))
            )
            login_field.clear()
            login_field.send_keys(login)
            
            # Ввод пароля
            password_field = self.driver.find_element(By.NAME, "login_pw")
            password_field.clear()
            password_field.send_keys(password)
            
            # Нажатие кнопки входа
            login_button = self.driver.find_element(By.ID, "msg_btn_login")
            login_button.click()
            
            logger.info("Успешная авторизация")
            return True
            
        except TimeoutException:
            logger.error("Таймаут при авторизации - элементы не найдены")
            return False
        except Exception as e:
            logger.error(f"Ошибка при авторизации: {e}")
            return False
    
    def navigate_to_subject(self, subject_name, is_first=True):
        try:
            if not is_first:
                home_link = WebDriverWait(self.driver, self.wait_timeout).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "ホーム"))
                )
                home_link.click()
                time.sleep(3)
            
            # Ожидание списка предметов
            portal_div = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "subject_list"))
            )
            
            # Поиск и клик по предмету
            lesson_link = portal_div.find_element(By.LINK_TEXT, subject_name)
            lesson_link.click()
            
            # Переход к урокам
            lesson_tab = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "授業"))
            )
            lesson_tab.click()
            
            time.sleep(5)
            logger.info(f"Успешный переход к предмету: {subject_name}")
            return True
            
        except TimeoutException:
            logger.error(f"Таймаут при переходе к предмету: {subject_name}")
            return False
        except NoSuchElementException:
            logger.error(f"Предмет не найден: {subject_name}")
            return False
        except Exception as e:
            logger.error(f"Ошибка при переходе к предмету {subject_name}: {e}")
            return False
    
    def open_lesson_blocks(self):
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "lesson_name"))
            )
            time.sleep(2)
            
            lesson_blocks = self.driver.find_elements(By.CLASS_NAME, "lesson_name")
            opened_lessons = 0
            
            for i in range(1, 16):
                lesson_number = f"第{i}回"
                
                for block in lesson_blocks:
                    if lesson_number in block.text:
                        try:
                            time.sleep(0.5)
                            block.click()
                            opened_lessons += 1
                            logger.info(f"Открыт блок урока: {lesson_number}")
                            time.sleep(1)
                            break
                        except Exception as e:
                            logger.warning(f"Не удалось открыть блок {lesson_number}: {e}")
                            break
                else:
                    logger.info(f"Блок урока {lesson_number} не найден")
            
            logger.info(f"Открыто блоков уроков: {opened_lessons}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при открытии блоков уроков: {e}")
            return False
    
    @contextmanager
    def video_window_context(self, original_window):
        video_window = None
        try:
            # Поиск нового окна
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    video_window = window_handle
                    self.driver.switch_to.window(video_window)
                    logger.debug("Переключение на окно видео")
                    break
            
            yield video_window
            
        finally:
            # Закрытие окна видео и возврат к основному
            if video_window and video_window in self.driver.window_handles:
                self.driver.close()
            
            if original_window in self.driver.window_handles:
                self.driver.switch_to.window(original_window)
    
    def process_videos(self):
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bw td.state_iconl"))
            )
            
            original_window = self.driver.current_window_handle
            videos_watched = 0
            consecutive_failures = 0
            max_consecutive_failures = 10
            
            while True:
                try:
                    video_blocks = self.driver.find_elements(By.CSS_SELECTOR, "div.type_bw")
                    found_unwatched = False
                    current_batch_unavailable = 0
                    
                    for block in video_blocks:
                        try:
                            icon_cell = block.find_element(By.CSS_SELECTOR, "td.state_iconl img")
                            src = icon_cell.get_attribute("src")
                            
                            contents_name_cell = block.find_element(By.CSS_SELECTOR, "td.contents_name a")
                            
                            if "sttop_iconl_yet.gif" in src:
                                found_unwatched = True
                                consecutive_failures = 0 
                                
                                video_title = contents_name_cell.text
                                videos_watched += 1
                                logger.info(f"Найдено непросмотренное видео {videos_watched}: {video_title}")
                                
                                contents_name_cell.click()
                                time.sleep(self.video_open_delay)
                                
                                with self.video_window_context(original_window) as video_window:
                                    if video_window:
                                        time.sleep(3) 
                                        logger.info(f"Успешно просмотрено видео {videos_watched}: {video_title}")
                                    else:
                                        logger.warning(f"Не удалось открыть видео {videos_watched}: {video_title}")
                                        videos_watched -= 1
                                
                                time.sleep(self.video_close_delay)
                                break
                            else:
                                continue
                                
                        except NoSuchElementException:
                            current_batch_unavailable += 1
                            continue
                        except Exception as e:
                            logger.error(f"Ошибка при обработке видео: {e}")
                            consecutive_failures += 1
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                            continue
                    
                    if current_batch_unavailable > 0:
                        logger.debug(f"Пропущено блоков без видео или уже просмотренных: {current_batch_unavailable}")
                    
                    if not found_unwatched:
                        logger.info("Все доступные видео просмотрены")
                        break
                    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(f"Слишком много ошибок подряд ({consecutive_failures}). Завершение обработки.")
                        break
                        
                except Exception as e:
                    logger.error(f"Ошибка при поиске видео: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error("Критическое количество ошибок. Прекращение обработки.")
                        break
                    time.sleep(5)
                    continue
            
            return videos_watched
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке видео: {e}")
            return 0
    
    def process_subject(self, subject_name, is_first=True):
        logger.info(f"Начало обработки предмета: {subject_name}")
        
        if not self.navigate_to_subject(subject_name, is_first):
            return 0
        
        if not self.open_lesson_blocks():
            return 0
        
        videos_watched = self.process_videos()
        logger.info(f"Просмотрено видео для предмета '{subject_name}': {videos_watched}")
        
        return videos_watched
    
    def run_automation(self):
        if not self.setup_driver():
            return
        
        try:
            if not self.login():
                return
            
            total_videos = 0
            
            for subject_index, subject_name in enumerate(subject_names):
                is_first = subject_index == 0
                videos_count = self.process_subject(subject_name, is_first)
                total_videos += videos_count
                
                if subject_index == len(subject_names) - 1:
                    logger.info("Все предметы обработаны")
            
            logger.info(f"Общее количество просмотренных видео: {total_videos}")
            
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            time.sleep(10)
            if self.driver:
                self.driver.quit()
                logger.info("Драйвер закрыт")

if __name__ == "__main__":
    try:
        automation = VideoAutomation()
        automation.run_automation()
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")