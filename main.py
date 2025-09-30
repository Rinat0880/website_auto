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
import subprocess
from webdriver_manager.chrome import ChromeDriverManager
import shutil

def find_system_chromedriver():
    """Ищем chromedriver в PATH или в стандартных локациях."""
    candidates = [
        shutil.which("chromedriver"),
        "/usr/local/bin/chromedriver",
        "/usr/bin/chromedriver",
        "/opt/google/chrome/chromedriver",
    ]
    for p in candidates:
        if p and shutil.os.path.exists(p):
            return p
    return None

def find_chrome_binary():
    """Пробуем найти бинарник Google Chrome / Chromium."""
    for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


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

try:
    from config import login, password, subject_names, mode, AI_api_key
except ImportError:
    logger.error(
        "Не удалось импортировать config.py. Проверьте наличие файла и параметров."
    )
    exit(1)

# VALID_MODES = ["video", "test"]
# if mode not in VALID_MODES:
#     logger.error(f"Некорректный режим '{mode}'. Допустимые режимы: {VALID_MODES}") -- russ pidor
#     exit(1)


class AITestSolver:

    def __init__(self, api_key=None):
        self.api_key = api_key or AI_api_key
        self.api_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        # self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.current_test_type = None  
        logger.info("Инициализирован ИИ решатель тестов с AI API")
    
    def determine_test_type(self, driver):
        try:
            self.current_test_type = None
            
            driver.switch_to.default_content()
            frame_main = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "frame_main"))
            )
            driver.switch_to.frame(frame_main)
            
            try:
                is_text_answer = driver.execute_script("return typeof hasTextAnswer !== 'undefined' && hasTextAnswer === true;")
                if is_text_answer:
                    self.current_test_type = "text_answer"
                    print("Определен тип теста: TEXT ANSWER - этот тип не поддерживается")
                    logger.warning("Обнаружен тест с текстовым ответом, который не поддерживается")
                    return "text_answer"
            except Exception as e:
                print(f"Ошибка при проверке на текстовый ответ: {e}")
        
            
            print("Определяем тип теста...")
            
            checkbox_elements = driver.find_elements(By.CLASS_NAME, "form_checkbox")
            if checkbox_elements:
                self.current_test_type = "checkbox"
                print("Определен тип теста: CHECKBOX")
                return "checkbox"
            
            radio_elements = driver.find_elements(By.CLASS_NAME, "form_radio")
            if radio_elements:
                self.current_test_type = "radio"
                print("Определен тип теста: RADIO")
                return "radio"
            
            iframe_inlist = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "inlist"))
            )
            driver.switch_to.frame(iframe_inlist)
            
            select_element = driver.find_element(By.ID, "ans_1")
            if select_element and select_element.tag_name == "select":
                self.current_test_type = "select"
                print("Определен тип теста: SELECT")
                return "select"
                
            self.current_test_type = "radio"
            print("Тип теста не определен, используется по умолчанию: RADIO")
            return "radio"
            
        except Exception as e:
            print(f"Ошибка при определении типа теста: {e}")
            self.current_test_type = "radio" 
            return "radio"
    
    def extract_question_data(self, driver):
        try:
            test_type = self.determine_test_type(driver)
            
            # If this is a text answer test, return empty data to signal skipping
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

            print("2: Ищу варианты ответов... и переходим на мейн")
            driver.switch_to.default_content()
            frame_main = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "frame_main"))
            )
            driver.switch_to.frame(frame_main) 
            
            if test_type == "checkbox":
                option_elements = driver.find_elements(
                    By.XPATH, '//label[starts-with(@for, "chk_")]'
                )
                for element in option_elements:
                    print("нашёл вариант (checkbox):", element.text.strip())
                    question_data['options'].append(element.text.strip())
                    
            if test_type == "radio":      
                option_elements = driver.find_elements(
                    By.XPATH, '//label[starts-with(@for, "rdo_")]'
                )
                for element in option_elements:
                    print("нашёл вариант (radio):", element.text.strip())
                    question_data['options'].append(element.text.strip())
                    
            iframe_inlist = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "inlist"))
            )
            print("переходим в инлист")
            driver.switch_to.frame(iframe_inlist)
                    
            if test_type == "select":
                print("Обрабатываем SELECT тест...")
                script = f"return document.getElementById('ans_1').length"
                len_options = driver.execute_script(script)
                
                for i in range(1, len_options):
                    script = f"return document.getElementById('ans_1')[{i}].text"
                    option_text = driver.execute_script(script)
                    print(f"нашёл вариант (select): {option_text}")
                    question_data['options'].append(option_text)

            print("4: Ищу текст вопроса")
            question_elements = driver.find_elements(By.CLASS_NAME, "iframe_body")
            if question_elements:
                question_data['question_text'] = question_elements[0].text.strip()
                print("вопрос: ", question_data)

            return question_data

        except Exception as e:
            print(f"Ошибка при извлечении: {type(e)} — {e}")
            return None


    
    def solve_question(self, question_data):
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
            #     "model": "deepseek/deepseek-r1:free",
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
                print("Ответ от ИИ: ", result)

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
        try:
            time.sleep(3)
            driver.switch_to.default_content()
            print("пытаемся перейти в фрейм_мейн")

            frame_main = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "frame_main"))
            )
            driver.switch_to.frame(frame_main)
            print("попали)")

            if self.current_test_type == "checkbox":
                for option_number in option_numbers:
                    script = f"""
                    var checkboxes = document.getElementsByClassName("form_checkbox");
                    if (checkboxes.length >= {option_number}) {{
                        checkboxes[{option_number - 1}].click();
                        console.log("clicked checkbox option {option_number}");
                        return true;
                    }} else {{
                        console.log("checkbox option {option_number} not found");
                        return false;
                    }}
                    """
                    print(script)
                    result = driver.execute_script(script)
                    print(result)
                    time.sleep(1)
                    
            elif self.current_test_type == "radio":
                for option_number in option_numbers:
                    script = f"""
                    var radios = document.getElementsByClassName("form_radio");
                    if (radios.length >= {option_number}) {{
                        radios[{option_number - 1}].click();
                        console.log("clicked radio option {option_number}");
                        return true;
                    }} else {{
                        console.log("radio option {option_number} not found");
                        return false;
                    }}
                    """
                    print(script)
                    result = driver.execute_script(script)
                    print(result)
                    time.sleep(1)
                    
            elif self.current_test_type == "select":
                print("Обрабатываем SELECT выбор...")
                iframe_inlist = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "inlist"))
                )
                print("переходим в инлист")
                driver.switch_to.frame(iframe_inlist)
    
                for i, option_number in enumerate(option_numbers, 1):
                    script = f"""
                    var select = document.getElementById("ans_{i}");
                    if (select && select.length >= {option_number}) {{
                        select.selectedIndex = {option_number};
                        console.log("selected option {option_number} for ans_{i}");
                        return true;
                    }} else {{
                        console.log("select ans_{i} not found or option {option_number} not available");
                        return false;
                    }}
                    """
                    print(script)
                    result = driver.execute_script(script)
                    print(result)
                    time.sleep(0.5)
    
                driver.execute_script("chgAnswer();")
                print("Вызван chgAnswer() для обновления результата")

            logger.info(f"Выбраны варианты: {option_numbers} для типа теста: {self.current_test_type}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при выборе ответов: {e}")
            return False
    
    def submit_answer(self, driver):
        try:
            self.current_test_type = None

            driver.switch_to.default_content()                                 
            print("пытаемся перейти в фрейм_ктрл")                                  
            frame_ctrl = driver.find_element(By.NAME, "frame_ctrl")
            driver.switch_to.frame(frame_ctrl)
            print("попали)")

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



class CampusAutomation:
    def __init__(self, chromedriver_path="chromedriver.exe"):
        self.chromedriver_path = chromedriver_path
        self.driver = None
        self.wait_timeout = 15
        self.video_open_delay = 10
        self.video_close_delay = 10
        self.test_open_delay = 10
        self.test_delay = 5
        self.mode = mode
        self.ai_solver = AITestSolver() 
        self.failed_tests = {}
        
    def find_system_chromedriver():
        """Ищем chromedriver в PATH или в стандартных локациях."""
        candidates = [
            shutil.which("chromedriver"),
            "/usr/local/bin/chromedriver",
            "/usr/bin/chromedriver",
            "/opt/google/chrome/chromedriver",
        ]
        for p in candidates:
            if p and shutil.os.path.exists(p):
                return p
        return None

    def find_chrome_binary():
        """Попробуем найти бинарник Google Chrome / Chromium."""
        for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser"):
            path = shutil.which(name)
            if path:
                return path
        return None

    def setup_driver(self):
        """
        Попытки инициализации драйвера в порядке:
        1) webdriver-manager (скачать подходящий chromedriver)
        2) системный chromedriver (PATH или стандартные пути)
        Если ни один вариант не сработал — логируем и возвращаем False.
        """
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
            chrome_options.add_argument("--headless=new")

            # если есть бинарник хрома, укажем его (полезно на системах с нестандартным расположением)
            chrome_bin = find_chrome_binary()
            if chrome_bin:
                chrome_options.binary_location = chrome_bin
                logger.debug(f"Найден бинарник Chrome: {chrome_bin}")

            # 1) Попробуем webdriver-manager (скачает подходящую версию chromedriver)
            try:
                driver_path = ChromeDriverManager().install()
                logger.info(f"Используем chromedriver от webdriver-manager: {driver_path}")
                service = Service(executable_path=driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                # mask webdriver property
                self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                logger.info("Драйвер успешно инициализирован через webdriver-manager")
                return True
            except Exception as e_wm:
                logger.warning(f"webdriver-manager не сработал: {e_wm}. Попробуем системный chromedriver...")

            # 2) Попробуем системный chromedriver (PATH или стандартные пути)
            system_driver = find_system_chromedriver()
            if system_driver:
                try:
                    logger.info(f"Пытаемся использовать системный chromedriver: {system_driver}")
                    service = Service(executable_path=system_driver)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                    self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                    logger.info("Драйвер успешно инициализирован через системный chromedriver")
                    return True
                except Exception as e_sys:
                    logger.error(f"Не удалось инициализировать системный chromedriver ({system_driver}): {e_sys}")

            # Ничего не помогло — строим понятную подсказку пользователю
            logger.error(
                "Не удалось получить chromedriver. Возможные варианты решения:\n"
                "  1) Установить chromedriver из репозитория/aur:\n"
                "       sudo pacman -S chromedriver                # если доступно\n"
                "       yay -S chromedriver                         # через AUR (Garuda)\n"
                "  2) Установить chromedriver вручную (см. chrome-for-testing) и поместить в /usr/local/bin:\n"
                "       wget <url-to-chromedriver.zip>\n"
                "       unzip chromedriver-linux64.zip\n"
                "       sudo mv chromedriver /usr/local/bin/\n"
                "       sudo chmod +x /usr/local/bin/chromedriver\n"
                "  3) Обновить webdriver-manager и selenium в venv:\n"
                "       pip install -U webdriver-manager selenium\n"
                "  4) Убедиться, что установлен Google Chrome и его путь обнаруживается (which google-chrome)\n"
            )
            return False

        except Exception as e:
            logger.error(f"Фатальная ошибка при инициализации драйвера: {e}")
            return False

    def login(self):
        try:
            self.driver.get("https://elcampus.otemae.ac.jp/")

            # ожидание поля логина
            login_field = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.NAME, "login_id"))
            )
            login_field.clear()
            login_field.send_keys(login)

            # ввод пароля
            password_field = self.driver.find_element(By.NAME, "login_pw")
            password_field.clear()
            password_field.send_keys(password)

            # нажатие кнопки входа
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

            # ожидание списка предметов
            portal_div = WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located((By.CLASS_NAME, "subject_list"))
            )

            # поиск и клик по предмету
            lesson_link = portal_div.find_element(By.LINK_TEXT, subject_name)
            lesson_link.click()

            # переход к урокам
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
            time.sleep(1)

            phase_codes = self.driver.execute_script("return typeof phaseCodes !== 'undefined' ? phaseCodes : null;")
            if not phase_codes:
                logger.error("Массив phaseCodes не найден на странице")
                return False

            opened = 0
            for code in phase_codes:
                try:
                    self.driver.execute_script(f"clickTitle('{code}', false);")
                    logger.info(f"Открыт блок урока с ID: {code}")
                    opened += 1
                except Exception as e:
                    logger.warning(f"Не удалось открыть блок с ID {code}: {e}")

            logger.info(f"Всего открыто блоков: {opened}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при открытии блоков уроков: {e}")
            return False

    @contextmanager
    def video_window_context(self, original_window):
        video_window = None
        try:
            # поиск нового окна
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    video_window = window_handle
                    self.driver.switch_to.window(video_window)
                    logger.debug("Переключение на окно видео")
                    break

            yield video_window

        finally:
            # закрытие окна видео и возврат к основному
            if video_window and video_window in self.driver.window_handles:
                self.driver.close()

            if original_window in self.driver.window_handles:
                self.driver.switch_to.window(original_window)

    @contextmanager
    def test_window_context(self, original_window):
        test_window = None
        try:
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    test_window = window_handle
                    self.driver.switch_to.window(test_window)
                    logger.debug("Переключение на окно теста")
                    break

            yield test_window

        finally:
            if test_window and test_window in self.driver.window_handles:
                self.driver.close()

            if original_window in self.driver.window_handles:
                self.driver.switch_to.window(original_window)

    def solve_test_with_ai(self, test_title):
        try:
            questions_solved = 0
            max_questions = 50  

            while questions_solved < max_questions:
                question_data = self.ai_solver.extract_question_data(self.driver)

                if question_data and question_data['question_type'] == 'text_answer':
                    logger.warning(f"Тест '{test_title}' содержит текстовые ответы, пропускаем")
                    return "text_answer_skip"  

                if not question_data or not question_data['question_text']:
                    logger.info("Вопросы закончились или тест завершен")
                    break

                try:
                    selected_option = self.ai_solver.solve_question(question_data)
                except RuntimeError as e:
                    if str(e) == "Лимит исчерпан":
                        logger.error("Остановка тестов из-за превышения дневного лимита Gemini API")
                        return "quota_exceeded"
                    else:
                        raise  

                if self.ai_solver.select_answer(self.driver, selected_option):
                    time.sleep(1)

                    submit_result = self.ai_solver.submit_answer(self.driver)

                    if submit_result == "next_question":
                        questions_solved += 1
                        logger.info(f"Решен вопрос {questions_solved} в тесте: {test_title}")
                        time.sleep(self.test_delay)
                    elif submit_result == "test_completed":
                        questions_solved += 1
                        logger.info(f"Тест '{test_title}' завершен после {questions_solved} вопросов")
                        return "completed"  
                    else:
                        logger.warning("Не удалось отправить ответ")
                        return "failed"  
                else:
                    logger.warning("Не удалось выбрать ответ")
                    return "failed"  

            if questions_solved == 0:
                return "failed"

            logger.info(f"Решено вопросов в тесте '{test_title}': {questions_solved}")
            return "completed" if questions_solved > 0 else "failed"

        except Exception as e:
            logger.error(f"Ошибка при решении теста через ИИ: {e}")
            return "failed"
        
    def process_videos(self):
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.type_bw td.state_iconl")
                )
            )

            original_window = self.driver.current_window_handle
            videos_watched = 0
            consecutive_failures = 0
            max_consecutive_failures = 10

            while True:
                try:
                    video_blocks = self.driver.find_elements(
                        By.CSS_SELECTOR, "div.type_bw"
                    )
                    found_unwatched = False
                    current_batch_unavailable = 0

                    for block in video_blocks:
                        try:
                            icon_cell = block.find_element(
                                By.CSS_SELECTOR, "td.state_iconl img"
                            )
                            src = icon_cell.get_attribute("src")

                            contents_name_cell = block.find_element(
                                By.CSS_SELECTOR, "td.contents_name a"
                            )

                            if (
                                "sttop_iconl_yet.gif" in src
                                or "sttop_iconl_notachieve.gif" in src
                            ):
                                found_unwatched = True
                                consecutive_failures = 0

                                video_title = contents_name_cell.text
                                videos_watched += 1
                                logger.info(
                                    f"Найдено непросмотренное видео {videos_watched}: {video_title}"
                                )

                                contents_name_cell.click()
                                time.sleep(self.video_open_delay)

                                with self.video_window_context(
                                    original_window
                                ) as video_window:
                                    if video_window:
                                        time.sleep(3)
                                        logger.info(
                                            f"Успешно просмотрено видео {videos_watched}: {video_title}"
                                        )
                                    else:
                                        logger.warning(
                                            f"Не удалось открыть видео {videos_watched}: {video_title}"
                                        )
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
                        logger.debug(
                            f"Пропущено блоков без видео или уже просмотренных: {current_batch_unavailable}"
                        )

                    if not found_unwatched:
                        logger.info("Все доступные видео просмотрены")
                        break

                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            f"Слишком много ошибок подряд ({consecutive_failures}). Завершение обработки."
                        )
                        break

                except Exception as e:
                    logger.error(f"Ошибка при поиске видео: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            "Критическое количество ошибок. Прекращение обработки."
                        )
                        break
                    time.sleep(5)
                    continue

            return videos_watched

        except Exception as e:
            logger.error(f"Критическая ошибка при обработке видео: {e}")
            return 0

    def process_tests(self, subject_name):
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.type_bt, div.type_bw")
                )
            )
    
            if subject_name not in self.failed_tests:
                self.failed_tests[subject_name] = []
    
            tests_processed = 0
            consecutive_failures = 0
            max_consecutive_failures = 10
            test_attempt_count = {}
    
            while True:
                try:
                    test_blocks = self.driver.find_elements(
                        By.CSS_SELECTOR, "div.type_bt"
                    )
                    found_unfinished = False
                    current_batch_unavailable = 0
    
                    for block in test_blocks:
                        try:
                            icon_cell = block.find_element(
                                By.CSS_SELECTOR, "td.state_iconl img"
                            )
                            src = icon_cell.get_attribute("src")

                            contents_name_cell = block.find_element(
                                By.CSS_SELECTOR, "td.contents_name a"
                            )
                            test_title = contents_name_cell.text.strip()

                            if test_title in self.failed_tests[subject_name]:
                                logger.info(f"Пропускаем ранее неудачно решенный тест: {test_title}")
                                continue

                            if (
                                "sttop_iconl_yet.gif" in src
                                or "sttop_iconl_notachieve.gif" in src
                            ):
                                if test_title not in test_attempt_count:
                                    test_attempt_count[test_title] = 0

                                test_attempt_count[test_title] += 1

                                if test_attempt_count[test_title] > 1:  
                                    logger.warning(f"Превышено количество попыток для теста: {test_title}")
                                    self.failed_tests[subject_name].append(test_title)
                                    continue

                                found_unfinished = True
                                consecutive_failures = 0

                                tests_processed += 1
                                logger.info(
                                    f"Найден незавершенный тест {tests_processed}: {test_title}"
                                )
    
                                original_window = self.driver.current_window_handle
    
                                contents_name_cell.click()
                                time.sleep(self.test_open_delay)
                                
                                WebDriverWait(self.driver, 10).until(lambda d: len(d.window_handles) > 1)
                                new_window = [w for w in self.driver.window_handles if w != original_window][0]
                                self.driver.switch_to.window(new_window)
    
                                test_success = False
                                with self.test_window_context(original_window) as test_window:
                                    if test_window:
                                        try:
                                            iframe1 = WebDriverWait(self.driver, 10).until(
                                                EC.presence_of_element_located((By.NAME, "frame_main"))
                                            )
                                            self.driver.switch_to.frame(iframe1)
                                            
                                            start_button_img = WebDriverWait(self.driver, 10).until(
                                                EC.element_to_be_clickable((By.XPATH, "//img[contains(@src, 'btn_do.gif')]"))
                                            )
                                            start_button_img.click()
                                            time.sleep(self.test_delay)
    
                                            logger.info(
                                                f"Нажата кнопка начала теста {tests_processed}: {test_title}"
                                            )
    
                                            # решение теста через ИИ
                                            test_success = self.solve_test_with_ai(test_title)
                                            if test_success == "completed":
                                                logger.info(f"Тест {tests_processed} успешно решен через ИИ: {test_title}")
                                            elif test_success == "text_answer_skip":
                                                logger.warning(f"Тест '{test_title}' содержит текстовые ответы, добавляем в список неудачных")
                                                self.failed_tests[subject_name].append(test_title)
                                            else: 
                                                logger.warning(f"Не удалось полностью решить тест {tests_processed}: {test_title}")
                                                self.failed_tests[subject_name].append(test_title)
    
                                        except TimeoutException:
                                            logger.warning(
                                                f"Кнопка начала теста не найдена для: {test_title}"
                                            )
                                            tests_processed -= 1
                                        except Exception as e:
                                            logger.error(
                                                f"Ошибка при выполнении теста {test_title}: {e}"
                                            )
                                            tests_processed -= 1
                                            self.failed_tests[subject_name].append(test_title)
                                    else:
                                        logger.warning(
                                            f"Не удалось открыть тест {tests_processed}: {test_title}"
                                        )
                                        tests_processed -= 1
                                        self.failed_tests[subject_name].append(test_title)
    
                                self.driver.refresh()
                                time.sleep(3)
                                break
    
                        except NoSuchElementException:
                            current_batch_unavailable += 1
                            continue
                        except Exception as e:
                            logger.error(f"Ошибка при обработке теста: {e}")
                            consecutive_failures += 1
                            continue
    
                    if current_batch_unavailable > 0:
                        logger.debug(
                            f"Пропущено блоков без тестов или уже завершенных: {current_batch_unavailable}"
                        )
    
                    if not found_unfinished:
                        logger.info("Все доступные тесты обработаны")
                        break
    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            f"Слишком много ошибок подряд ({consecutive_failures}). Завершение обработки."
                        )
                        break
    
                except Exception as e:
                    logger.error(f"Ошибка во внутреннем цикле обработки тестов: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        break
    
            if self.failed_tests[subject_name]:
                logger.warning(f"Не удалось решить {len(self.failed_tests[subject_name])} тестов в предмете '{subject_name}':")
                for failed_test in self.failed_tests[subject_name]:
                    logger.warning(f"  - {failed_test}")
    
            return tests_processed
    
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке тестов: {e}")
            return 0

    def process_subject(self, subject_name, is_first=True):
        logger.info(f"Начало обработки предмета: {subject_name} (режим: {self.mode})")

        if not self.navigate_to_subject(subject_name, is_first):
            return 0

        if not self.open_lesson_blocks():
            return 0

        if self.mode == "video":
            processed_count = self.process_videos()
            logger.info(
                f"Просмотрено видео для предмета '{subject_name}': {processed_count}"
            )
        elif self.mode == "test":
            processed_count = self.process_tests(subject_name)
            logger.info(
                f"Обработано тестов для предмета '{subject_name}': {processed_count}"
            )
        else:
            logger.error(f"Неизвестный режим: {self.mode}")
            return 0

        return processed_count

    def run_automation(self):
        if not self.setup_driver():
            return

        try:
            if not self.login():
                return

            logger.info(f"Запуск автоматизации в режиме: {self.mode}")
            total_processed = 0
            total_failed = 0

            for subject_index, subject_name in enumerate(subject_names):
                is_first = subject_index == 0
                processed_count = self.process_subject(subject_name, is_first)
                total_processed += processed_count

                if subject_index == len(subject_names) - 1:
                    logger.info("Все предметы обработаны")

            if self.mode == "video":
                logger.info(f"Общее количество просмотренных видео: {total_processed}")
            elif self.mode == "test":
                for subject, failed_tests in self.failed_tests.items():
                    total_failed += len(failed_tests)
                
                logger.info(f"Общее количество обработанных тестов: {total_processed}")
                logger.info(f"Общее количество непройденных тестов: {total_failed}")
                
                if total_failed > 0:
                    logger.warning("Список всех непройденных тестов:")
                    for subject, failed_tests in self.failed_tests.items():
                        if failed_tests:
                            logger.warning(f"  Предмет '{subject}' - {len(failed_tests)} тестов:")
                            for test in failed_tests:
                                logger.warning(f"    - {test}")

        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
        finally:
            time.sleep(10)
            if self.driver:
                self.driver.quit()
                logger.info("Драйвер закрыт")


if __name__ == "__main__":
    try:
        automation = CampusAutomation()
        automation.run_automation()
    except KeyboardInterrupt:
        logger.info("Программа прервана пользователем")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")