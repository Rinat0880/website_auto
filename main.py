import time
import logging
import json
import requests
import re
import sys 
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
    WebDriverException,
)
import shutil
import os
from webdriver_manager.chrome import ChromeDriverManager

# ============= ГЛОБАЛЬНЫЕ УТИЛИТЫ =============

def find_system_chromedriver():
    """Ищем chromedriver в PATH или в стандартных локациях."""
    candidates = [
        shutil.which("chromedriver"),
        "/usr/local/bin/chromedriver",
        "/usr/bin/chromedriver",
        "/opt/google/chrome/chromedriver",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def find_chrome_binary():
    """Пробуем найти бинарник Google Chrome / Chromium."""
    for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None

# ============= НАСТРОЙКА ЛОГИРОВАНИЯ =============

LOG_LEVEL = logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("automation.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ============= ИМПОРТ КОНФИГУРАЦИИ =============

try:
    from config import login, password, subject_names, mode, AI_api_key, HEADLESS
except ImportError:
    logger.error(
        "Не удалось импортировать config.py. Проверьте наличие файла и параметров."
    )
    exit(1)

# ============= КЛАСС РЕШЕНИЯ ТЕСТОВ =============

class AITestSolver:

    def __init__(self, api_key=None):
        self.api_key = api_key or AI_api_key
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        # self.api_url = "https://openrouter.ai/api/v1/chat/completions"   - если есть ключ от опенроутерапи то можете им пользоваться
        self.current_test_type = None  
        logger.info("Инициализирован ИИ решатель тестов с AI API")
    
    def determine_test_type(self, driver):
        """Определение типа теста (checkbox, radio, select, text_answer)"""
        try:
            self.current_test_type = None
            
            driver.switch_to.default_content()
            frame_main = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "frame_main"))
            )
            driver.switch_to.frame(frame_main)
            
            # проверка на текстовый ответ (мы его пропускаем, зачем мне жопу рвать)
            try:
                is_text_answer = driver.execute_script(
                    "return typeof hasTextAnswer !== 'undefined' && hasTextAnswer === true;"
                )
                if is_text_answer:
                    self.current_test_type = "text_answer"
                    logger.warning("Обнаружен тест с текстовым ответом, который не поддерживается")
                    return "text_answer"
            except Exception as e:
                logger.debug(f"Ошибка при проверке на текстовый ответ: {e}")
            
            # проверка других рабочих типов
            checkbox_elements = driver.find_elements(By.CLASS_NAME, "form_checkbox")
            if checkbox_elements:
                self.current_test_type = "checkbox"
                logger.info("Определен тип теста: CHECKBOX")
                return "checkbox"
            
            radio_elements = driver.find_elements(By.CLASS_NAME, "form_radio")
            if radio_elements:
                self.current_test_type = "radio"
                logger.info("Определен тип теста: RADIO")
                return "radio"
            
            iframe_inlist = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "inlist"))
            )
            driver.switch_to.frame(iframe_inlist)
            
            try:
                select_element = driver.find_element(By.ID, "ans_1")
                if select_element and select_element.tag_name == "select":
                    self.current_test_type = "select"
                    logger.info("Определен тип теста: SELECT")
                    return "select"
            except NoSuchElementException:
                pass
                
            self.current_test_type = "radio"
            logger.info("Тип теста не определен, используется по умолчанию: RADIO")
            return "radio"
            
        except Exception as e:
            logger.error(f"Ошибка при определении типа теста: {e}")
            self.current_test_type = "radio" 
            return "radio"
    
    def extract_question_data(self, driver):
        """Извлечение данных вопроса и вариантов ответа"""
        try:
            test_type = self.determine_test_type(driver)
            
            # пропуск текстовых ответов
            if test_type == "text_answer":
                return {
                    'question_text': 'TEXT_ANSWER_NOT_SUPPORTED',
                    'options': [],
                    'question_type': 'text_answer'
                }
                
            question_data = {
                'question_text': '',
                'options': [],
                'question_type': test_type
            }

            # переход к frame_main
            driver.switch_to.default_content()
            frame_main = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "frame_main"))
            )
            driver.switch_to.frame(frame_main) 
            
            # извлечение вариантов ответа
            if test_type == "checkbox":
                option_elements = driver.find_elements(
                    By.XPATH, '//label[starts-with(@for, "chk_")]'
                )
                for element in option_elements:
                    question_data['options'].append(element.text.strip())
                    
            elif test_type == "radio":      
                option_elements = driver.find_elements(
                    By.XPATH, '//label[starts-with(@for, "rdo_")]'
                )
                for element in option_elements:
                    question_data['options'].append(element.text.strip())
                    
            elif test_type == "select":
                iframe_inlist = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "inlist"))
                )
                driver.switch_to.frame(iframe_inlist)
                
                script = "return document.getElementById('ans_1').length"
                len_options = driver.execute_script(script)
                
                for i in range(1, len_options):
                    script = f"return document.getElementById('ans_1')[{i}].text"
                    option_text = driver.execute_script(script)
                    question_data['options'].append(option_text)
                
                # возврат к frame_main для извлечения текста вопроса (потому что на строчке 182 мы заходили в фрейм инлист)
                driver.switch_to.default_content()
                driver.switch_to.frame(frame_main)

            # извлечение текста вопроса
            question_elements = driver.find_elements(By.CLASS_NAME, "iframe_body")
            if question_elements:
                question_data['question_text'] = question_elements[0].text.strip()

            logger.debug(f"Извлечены данные вопроса: {question_data['question_type']}, "
                        f"{len(question_data['options'])} вариантов")
            return question_data

        except Exception as e:
            logger.error(f"Ошибка при извлечении данных вопроса: {type(e)} — {e}")
            return None
    
    def solve_question(self, question_data):
        """Решение вопроса через AI API"""
        try:
            if not question_data or not question_data['question_text'] or not question_data['options']:
                logger.warning("Недостаточно данных для решения вопроса")
                return [1]

            options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question_data['options'])])
            prompt = f"""Ты эксперт по японским академическим тестам. Проанализируй вопрос и выбери правильный ответ.

Вопрос: {question_data['question_text']}

Варианты ответов:
{options_text}

    Отвечай ТОЛЬКО номером правильного варианта (например: 1 2 4 или 1,3). Никаких объяснений не нужно."""
    
            # request_data = {
                # "model": "deepseek/deepseek-r1:free",                                                              #----это для опенроутер апи
            #     "messages": [
            #         {
            #             "role": "user",
            #             "content": prompt
            #         }
            #     ]
            # }

            # headers = {
            #     'Content-Type': 'application/json',
            #     'Authorization': f'Bearer {self.api_key}'
            # }

            # response = requests.post(self.api_url, headers=headers, json=request_data, timeout=30)

            # if response.status_code == 200:
            #     result = response.json()
            #     print("Ответ от ИИ: ", result)

            #     content = result['choices'][0]['message']['content'].strip()
            #     numbers = [int(n) for n in re.findall(r'\d+', content)]
            #     valid_numbers = [n for n in numbers if 1 <= n <= len(question_data['options'])]

            #     if valid_numbers:
            #         logger.info(f"ИИ выбрал варианты: {valid_numbers}")
            #         return valid_numbers
            #     else:
            #         logger.warning(f"AI вернул неверные номера: {numbers}")
            #         return [1]

            request_data = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ]
            }

            headers = {
                'Content-Type': 'application/json',
                'X-goog-api-key': self.api_key
            }

            response = requests.post(self.api_url, headers=headers, json=request_data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    
                    numbers = [int(n) for n in re.findall(r'\d+', content)]
                    valid_numbers = [n for n in numbers if 1 <= n <= len(question_data['options'])]

                    if valid_numbers:
                        logger.info(f"ИИ выбрал варианты: {valid_numbers}")
                        return valid_numbers
                    else:
                        logger.warning(f"AI вернул неверные номера: {numbers}")
                        return [1]
                else:
                    logger.warning("Пустой ответ от AI API")
                    return [1]

            elif response.status_code == 429:
                logger.error("Превышен дневной лимит (200 запросов) к Gemini API. Остановка всех тестов.")
                sys.exit(1)
            else:
                logger.error(f"Ошибка AI API: {response.status_code} - {response.text}")
                return [1]

        except requests.exceptions.Timeout:
            logger.error("Таймаут при запросе к AI API")
            return [1]
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при обращении к AI API: {e}")
            return [1]
        except Exception as e:
            logger.error(f"Неожиданная ошибка при решении вопроса через AI: {e}")
            return [1]
    
    def select_answer(self, driver, option_numbers):
        """Выбор ответа в тесте"""
        try:
            time.sleep(3)
            driver.switch_to.default_content()

            frame_main = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "frame_main"))
            )
            driver.switch_to.frame(frame_main)

            if self.current_test_type == "checkbox":
                for option_number in option_numbers:
                    script = f"""
                    var checkboxes = document.getElementsByClassName("form_checkbox");
                    if (checkboxes.length >= {option_number}) {{
                        checkboxes[{option_number - 1}].click();
                        return true;
                    }}
                    return false;
                    """
                    driver.execute_script(script)
                    time.sleep(0.5)
                    
            elif self.current_test_type == "radio":
                option_number = option_numbers[0]  
                script = f"""
                var radios = document.getElementsByClassName("form_radio");
                if (radios.length >= {option_number}) {{
                    radios[{option_number - 1}].click();
                    return true;
                }}
                return false;
                """
                driver.execute_script(script)
                time.sleep(0.5)
                    
            elif self.current_test_type == "select":
                iframe_inlist = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "inlist"))
                )
                driver.switch_to.frame(iframe_inlist)
    
                for i, option_number in enumerate(option_numbers, 1):
                    script = f"""
                    var select = document.getElementById("ans_{i}");
                    if (select && select.length >= {option_number}) {{
                        select.selectedIndex = {option_number};
                        return true;
                    }}
                    return false;
                    """
                    driver.execute_script(script)
                    time.sleep(0.5)
    
                driver.execute_script("chgAnswer();")

            logger.info(f"Выбраны варианты: {option_numbers} для типа теста: {self.current_test_type}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при выборе ответов: {e}")
            return False
    
    def submit_answer(self, driver):
        """Отправка ответа и переход к следующему вопросу"""
        try:
            self.current_test_type = None

            driver.switch_to.default_content()
            frame_ctrl = driver.find_element(By.NAME, "frame_ctrl")
            driver.switch_to.frame(frame_ctrl)

            is_forward_enabled = driver.execute_script("""
                const btn = document.getElementById('btn_enabled_forward');
                return btn && btn.style.display === 'block';
            """)

            if is_forward_enabled:
                driver.execute_script("ctrlExecute('forward')")
                logger.info("Выполнен переход на следующий вопрос")
                time.sleep(1)
                return "next_question" 
            else:
                driver.execute_script("ctrlExecute('mark')")
                logger.info("Последний вопрос — тест завершён и отправлен")

                WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert.accept()
                logger.info("Alert с подтверждением принят")

                time.sleep(5)
                return "test_completed" 

        except Exception as e:
            logger.error(f"Ошибка при переходе/отправке: {e}")
            return False

# ============= КЛАСС АВТОМАТИЗАЦИИ =============

class CampusAutomation:
    """Основной класс автоматизации работы с Campus"""
    
    def __init__(self):
        self.driver = None
        self.wait_timeout = 15
        self.video_open_delay = 10
        self.video_close_delay = 10
        self.test_open_delay = 10
        self.test_delay = 5
        self.mode = mode
        self.ai_solver = AITestSolver() 
        self.failed_tests = {}

    def setup_driver(self):
        """Инициализация WebDriver с оптимизацией попыток"""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-translate")
            chrome_options.add_argument("--log-level=3") 
            if HEADLESS:
                chrome_options.add_argument("--headless=new")
                chrome_options.add_argument("--disable-gpu")

            # поиск Chrome binary
            chrome_bin = find_chrome_binary()
            if chrome_bin:
                chrome_options.binary_location = chrome_bin
                logger.debug(f"Найден бинарник Chrome: {chrome_bin}")

            # попытка 1: webdriver-manager
            try:
                logger.info("Попытка инициализации через webdriver-manager...")
                driver_path = ChromeDriverManager().install()
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                logger.info("Драйвер успешно инициализирован через webdriver-manager")
                return True
            except Exception as e_wm:
                logger.warning(f"webdriver-manager не сработал: {e_wm}")

            # попытка 2: системный chromedriver
            system_driver = find_system_chromedriver()
            if system_driver:
                try:
                    logger.info(f"Попытка использования системного chromedriver: {system_driver}")
                    service = Service(executable_path=system_driver)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    logger.info("Драйвер успешно инициализирован через системный chromedriver")
                    return True
                except Exception as e_sys:
                    logger.error(f"Системный chromedriver не сработал: {e_sys}")
            return False

        except Exception as e:
            logger.error(f"Фатальная ошибка при инициализации драйвера: {e}")
            return False

    def login(self):
        """Авторизация на сайте"""
        try:
            self.driver.get("https://elcampus.otemae.ac.jp/")

            login_field = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.NAME, "login_id"))
            )
            login_field.clear()
            login_field.send_keys(login)

            password_field = self.driver.find_element(By.NAME, "login_pw")
            password_field.clear()
            password_field.send_keys(password)

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
        """Переход к предмету"""
        try:
            if not is_first:
                home_link = WebDriverWait(self.driver, self.wait_timeout).until(
                    EC.element_to_be_clickable((By.LINK_TEXT, "ホーム"))
                )
                home_link.click()
                time.sleep(3)

            portal_div = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "subject_list"))
            )

            lesson_link = portal_div.find_element(By.LINK_TEXT, subject_name)
            lesson_link.click()

            lesson_tab = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "授業"))
            )
            lesson_tab.click()

            time.sleep(5)
            logger.info(f"Переход к предмету: {subject_name}")
            return True

        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Ошибка при переходе к предмету '{subject_name}': {e}")
            return False

    def open_lesson_blocks(self):
        """Открытие всех блоков уроков"""
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "lesson_name"))
            )
            time.sleep(1)

            phase_codes = self.driver.execute_script(
                "return typeof phaseCodes !== 'undefined' ? phaseCodes : null;"
            )
            if not phase_codes:
                logger.error("Массив phaseCodes не найден")
                return False

            for code in phase_codes:
                try:
                    self.driver.execute_script(f"clickTitle('{code}', false);")
                except Exception as e:
                    logger.debug(f"Не удалось открыть блок {code}: {e}")

            logger.info(f"Открыто блоков: {len(phase_codes)}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при открытии блоков: {e}")
            return False

    @contextmanager
    def video_window_context(self, original_window):
        """Контекстный менеджер для работы с окном видео"""
        video_window = None
        try:
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    video_window = window_handle
                    self.driver.switch_to.window(video_window)
                    break
            yield video_window
        finally:
            if video_window and video_window in self.driver.window_handles:
                self.driver.close()
            if original_window in self.driver.window_handles:
                self.driver.switch_to.window(original_window)

    @contextmanager
    def test_window_context(self, original_window):
        """Контекстный менеджер для работы с окном теста"""
        test_window = None
        try:
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    test_window = window_handle
                    self.driver.switch_to.window(test_window)
                    break
            yield test_window
        finally:
            if test_window and test_window in self.driver.window_handles:
                self.driver.close()
            if original_window in self.driver.window_handles:
                self.driver.switch_to.window(original_window)

    def solve_test_with_ai(self, test_title):
        """Решение теста с помощью AI"""
        try:
            questions_solved = 0
            max_questions = 50

            while questions_solved < max_questions:
                question_data = self.ai_solver.extract_question_data(self.driver)

                # пропуск текстовых ответов
                if question_data and question_data['question_type'] == 'text_answer':
                    logger.warning(f"Тест '{test_title}' содержит текстовые ответы, пропускаем")
                    return "text_answer_skip"

                if not question_data or not question_data['question_text']:
                    logger.info("Вопросы закончились")
                    break

                selected_option = self.ai_solver.solve_question(question_data)

                if self.ai_solver.select_answer(self.driver, selected_option):
                    time.sleep(1)
                    submit_result = self.ai_solver.submit_answer(self.driver)

                    if submit_result == "next_question":
                        questions_solved += 1
                        logger.info(f"Решен вопрос {questions_solved}/{max_questions}")
                        time.sleep(self.test_delay)
                    elif submit_result == "test_completed":
                        questions_solved += 1
                        logger.info(f"Тест завершен: {questions_solved} вопросов")
                        return "completed"
                    else:
                        return "failed"
                else:
                    logger.warning("Не удалось выбрать ответ")
                    return "failed"

            return "completed" if questions_solved > 0 else "failed"

        except Exception as e:
            logger.error(f"Ошибка при решении теста: {e}")
            return "failed"
        
    def process_videos(self):
        """Обработка видео"""
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

                    for block in video_blocks:
                        try:
                            icon_cell = block.find_element(By.CSS_SELECTOR, "td.state_iconl img")
                            src = icon_cell.get_attribute("src")
                            contents_name_cell = block.find_element(By.CSS_SELECTOR, "td.contents_name a")

                            if "sttop_iconl_yet.gif" in src or "sttop_iconl_notachieve.gif" in src:
                                found_unwatched = True
                                consecutive_failures = 0

                                video_title = contents_name_cell.text
                                videos_watched += 1
                                logger.info(f"[{videos_watched}] Просмотр видео: {video_title}")

                                contents_name_cell.click()
                                time.sleep(self.video_open_delay)

                                with self.video_window_context(original_window) as video_window:
                                    if video_window:
                                        time.sleep(3)
                                        logger.info(f"Просмотрено: {video_title}")
                                    else:
                                        logger.warning(f"Не удалось открыть: {video_title}")
                                        videos_watched -= 1

                                time.sleep(self.video_close_delay)
                                break

                        except NoSuchElementException:
                            continue
                        except Exception as e:
                            logger.error(f"Ошибка обработки видео: {e}")
                            consecutive_failures += 1
                            if original_window in self.driver.window_handles:
                                self.driver.switch_to.window(original_window)
                            continue

                    if not found_unwatched:
                        logger.info("Все видео просмотрены")
                        break

                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(f"Слишком много ошибок ({consecutive_failures})")
                        break

                except Exception as e:
                    logger.error(f"Ошибка поиска видео: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
                    time.sleep(5)

            return videos_watched

        except Exception as e:
            logger.error(f"Критическая ошибка обработки видео: {e}")
            return 0

    def process_tests(self, subject_name):
        """Обработка тестов"""
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.type_bt, div.type_bw"))
            )
    
            if subject_name not in self.failed_tests:
                self.failed_tests[subject_name] = []
    
            tests_processed = 0
            consecutive_failures = 0
            max_consecutive_failures = 10
            test_attempt_count = {}
    
            while True:
                try:
                    test_blocks = self.driver.find_elements(By.CSS_SELECTOR, "div.type_bt")
                    found_unfinished = False
    
                    for block in test_blocks:
                        try:
                            icon_cell = block.find_element(By.CSS_SELECTOR, "td.state_iconl img")
                            src = icon_cell.get_attribute("src")
                            contents_name_cell = block.find_element(By.CSS_SELECTOR, "td.contents_name a")
                            test_title = contents_name_cell.text.strip()

                            # пропуск ранее неудачных тестов
                            if test_title in self.failed_tests[subject_name]:
                                logger.debug(f"Пропускаем ранее неудачный тест: {test_title}")
                                continue

                            if "sttop_iconl_yet.gif" in src or "sttop_iconl_notachieve.gif" in src:
                                # ограничение попыток
                                if test_title not in test_attempt_count:
                                    test_attempt_count[test_title] = 0

                                test_attempt_count[test_title] += 1

                                if test_attempt_count[test_title] > 1:
                                    logger.warning(f"✗ Превышено число попыток: {test_title}")
                                    self.failed_tests[subject_name].append(test_title)
                                    continue

                                found_unfinished = True
                                consecutive_failures = 0
                                tests_processed += 1
                                
                                logger.info(f"[{tests_processed}] Обработка теста: {test_title}")
    
                                original_window = self.driver.current_window_handle
                                contents_name_cell.click()
                                time.sleep(self.test_open_delay)
                                
                                WebDriverWait(self.driver, 10).until(
                                    lambda d: len(d.window_handles) > 1
                                )
                                new_window = [w for w in self.driver.window_handles 
                                            if w != original_window][0]
                                self.driver.switch_to.window(new_window)
    
                                with self.test_window_context(original_window) as test_window:
                                    if test_window:
                                        try:
                                            # переход к frame и нажатие кнопки старта
                                            iframe1 = WebDriverWait(self.driver, 10).until(
                                                EC.presence_of_element_located((By.NAME, "frame_main"))
                                            )
                                            self.driver.switch_to.frame(iframe1)
                                            
                                            start_button_img = WebDriverWait(self.driver, 10).until(
                                                EC.element_to_be_clickable(
                                                    (By.XPATH, "//img[contains(@src, 'btn_do.gif')]")
                                                )
                                            )
                                            start_button_img.click()
                                            time.sleep(self.test_delay)
                                            
                                            logger.info(f"Тест запущен: {test_title}")
    
                                            # решение теста через AI
                                            test_result = self.solve_test_with_ai(test_title)
                                            
                                            if test_result == "completed":
                                                logger.info(f"Тест успешно решен: {test_title}")
                                            elif test_result == "text_answer_skip":
                                                logger.warning(f"Тест пропущен (текстовые ответы): {test_title}")
                                                self.failed_tests[subject_name].append(test_title)
                                            else:
                                                logger.warning(f"Тест не решен: {test_title}")
                                                self.failed_tests[subject_name].append(test_title)
    
                                        except TimeoutException:
                                            logger.warning(f"Кнопка старта не найдена: {test_title}")
                                            tests_processed -= 1
                                            self.failed_tests[subject_name].append(test_title)
                                        except Exception as e:
                                            logger.error(f"Ошибка выполнения теста '{test_title}': {e}")
                                            tests_processed -= 1
                                            self.failed_tests[subject_name].append(test_title)
                                    else:
                                        logger.warning(f"Не удалось открыть окно теста: {test_title}")
                                        tests_processed -= 1
                                        self.failed_tests[subject_name].append(test_title)
    
                                self.driver.refresh()
                                time.sleep(3)
                                break
    
                        except NoSuchElementException:
                            continue
                        except Exception as e:
                            logger.error(f"Ошибка обработки блока теста: {e}")
                            consecutive_failures += 1
                            continue
    
                    if not found_unfinished:
                        logger.info("Все доступные тесты обработаны")
                        break
    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(f"Слишком много ошибок ({consecutive_failures})")
                        break
    
                except Exception as e:
                    logger.error(f"Ошибка во внутреннем цикле: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
    
            # вывод статистики по неудачным тестам
            if self.failed_tests[subject_name]:
                logger.warning(
                    f"Не решено {len(self.failed_tests[subject_name])} тестов "
                    f"в предмете '{subject_name}'"
                )
                for failed_test in self.failed_tests[subject_name]:
                    logger.warning(f"  • {failed_test}")
    
            return tests_processed
    
        except Exception as e:
            logger.error(f"Критическая ошибка обработки тестов: {e}")
            return 0

    def process_subject(self, subject_name, is_first=True):
        """Обработка одного предмета"""
        logger.info(f"{'='*60}")
        logger.info(f"Обработка предмета: {subject_name} (режим: {self.mode})")
        logger.info(f"{'='*60}")

        if not self.navigate_to_subject(subject_name, is_first):
            return 0

        if not self.open_lesson_blocks():
            return 0

        if self.mode == "video":
            processed_count = self.process_videos()
            logger.info(f"Просмотрено видео: {processed_count}")
        elif self.mode == "test":
            processed_count = self.process_tests(subject_name)
            logger.info(f"Обработано тестов: {processed_count}")
        else:
            logger.error(f"Неизвестный режим: {self.mode}")
            return 0

        return processed_count

    def run_automation(self):
        """Запуск полной автоматизации"""
        if not self.setup_driver():
            logger.error("Не удалось инициализировать драйвер")
            return

        try:
            if not self.login():
                logger.error("Не удалось авторизоваться")
                return

            logger.info(f"{'='*60}")
            logger.info(f"ЗАПУСК АВТОМАТИЗАЦИИ (режим: {self.mode})")
            logger.info(f"Предметов к обработке: {len(subject_names)}")
            logger.info(f"{'='*60}")
            
            total_processed = 0
            total_failed = 0

            for subject_index, subject_name in enumerate(subject_names):
                is_first = subject_index == 0
                processed_count = self.process_subject(subject_name, is_first)
                total_processed += processed_count

            # итоговая статистика
            logger.info(f"{'='*60}")
            logger.info(f"ИТОГИ")
            logger.info(f"{'='*60}")

            if self.mode == "video":
                logger.info(f"Всего просмотрено видео: {total_processed}")
                
            elif self.mode == "test":
                for subject, failed_tests in self.failed_tests.items():
                    total_failed += len(failed_tests)
                
                logger.info(f"Всего обработано тестов: {total_processed}")
                logger.info(f"Всего не решено тестов: {total_failed}")
                
                if total_failed > 0:
                    logger.warning(f"\n{'='*60}")
                    logger.warning("СПИСОК НЕРЕШЕННЫХ ТЕСТОВ")
                    logger.warning(f"{'='*60}")
                    for subject, failed_tests in self.failed_tests.items():
                        if failed_tests:
                            logger.warning(f"\n{subject} ({len(failed_tests)} тестов):")
                            for test in failed_tests:
                                logger.warning(f"  • {test}")

            logger.info(f"{'='*60}")

        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            time.sleep(10)
            if self.driver:
                self.driver.quit()
                logger.info("Драйвер закрыт")


# ============= ТОЧКА ВХОДА =============

if __name__ == "__main__":
    try:
        automation = CampusAutomation()
        automation.run_automation()
    except KeyboardInterrupt:
        logger.info("\nПрограмма прервана пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")