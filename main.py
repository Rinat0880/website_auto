import time
import logging
import json
import requests
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
        logger.info("Инициализирован ИИ решатель тестов с AI API")
    
    def extract_question_data(self, driver):
        try:
            question_data = {
                'question_text': '',
                'options': [],
                'question_type': 'multiple_choice'
            }

            try:
                driver.switch_to.default_content()  
                frame_main = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "frame_main"))
                )
                driver.switch_to.frame(frame_main)
            except Exception as e:
                print(f"")

            print("2: Ищу варианты ответов...")
            option_elements = driver.find_elements(
                By.XPATH, '//label[starts-with(@for, "rdo_")]'
            )
            for element in option_elements:
                print("нашёл вариант:", element.text.strip())
                question_data['options'].append(element.text.strip())

            print("3: Переключаюсь в inlist")
            iframe_inlist = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "inlist"))
            )
            driver.switch_to.frame(iframe_inlist)

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
                return 1
            
            options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(question_data['options'])])
            prompt = f"""Ты эксперт по японским академическим тестам. Проанализируй вопрос и выбери правильный ответ.

Вопрос: {question_data['question_text']}

Варианты ответов:
{options_text}

Отвечай ТОЛЬКО номером правильного варианта (1, 2, 3 или 4). Никаких объяснений не нужно."""

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
                    
                    # Извлекаем номер ответа
                    try:
                        selected_option = int(content)
                        if 1 <= selected_option <= len(question_data['options']):
                            logger.info(f"ии выбрал вариант {selected_option} из {len(question_data['options'])}")
                            return selected_option
                        else:
                            logger.warning(f"AI вернул неверный номер: {selected_option}")
                            return 1
                    except ValueError:
                        logger.warning(f"Не удалось извлечь номер из ответа AI: {content}")
                        return 1
                else:
                    logger.warning("Пустой ответ от AI API")
                    return 1
            else:
                logger.error(f"Ошибка AI API: {response.status_code} - {response.text}")
                return 1
                
        except requests.exceptions.Timeout:
            logger.error("Таймаут при запросе к AI API")
            return 1
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при обращении к AI API: {e}")
            return 1
        except Exception as e:
            logger.error(f"Неожиданная ошибка при решении вопроса через AI: {e}")
            return 1
    
    def select_answer(self, driver, option_number):
        while True:
            try:
                time.sleep(3)
                
                driver.switch_to.default_content()                                 
                print("пытаемся перейти в фрейм_мейн")                                  
                # frame_main = driver.find_element(By.NAME, "frame_main")            # только при поиске мы переходим на фрейм
                # driver.switch_to.frame(frame_main)
                frame_main = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "frame_main"))
                )
                driver.switch_to.frame(frame_main)
                print("попали)")
                
                script = f"""
                var radios = document.getElementsByClassName("form_radio");
                if (radios.length >= {option_number}) {{
                    radios[{option_number - 1}].click();
                    console.log("we in true");
                    return true;
                }} else {{
                    console.log("we in false");
                    return false;
                }}
                """
                print(script)
                result = driver.execute_script(script)
                print(result)
                time.sleep(10)
                if result:
                    logger.info(f"Выбран вариант ответа №{option_number} через click()")
                    return True
                else:
                    logger.warning(f"Вариант №{option_number} не найден среди радио-кнопок")
                    time.sleep(5)
            except Exception as e:
                logger.error(f"Ошибка при выборе ответа через click(): {e}")
        print("Nakaaaaaaaaaaaanetsta!!!!!!!!!")

    
    def submit_answer(self, driver):
        try:
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
            else:
                driver.execute_script("ctrlExecute('mark')")
                logger.info("Последний вопрос — тест завершён и отправлен")
            
                WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert.accept()
                logger.info("Alert с подтверждением принят")
                
                time.sleep(5)

                driver.close()  

                return True

            time.sleep(1)  
            return True
            

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
        self.ai_solver = AITestSolver()  # Инициализация ИИ решателя

    def setup_driver(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option(
                "excludeSwitches", ["enable-automation"]
            )
            chrome_options.add_experimental_option("useAutomationExtension", False)

            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--disable-translate")

            service = Service(executable_path=self.chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
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
                
                if not question_data or not question_data['question_text']:
                    logger.info("Вопросы закончились или тест завершен")
                    break
                
                selected_option = self.ai_solver.solve_question(question_data)
                
                if self.ai_solver.select_answer(self.driver, selected_option):
                    time.sleep(1)
                    
                    if self.ai_solver.submit_answer(self.driver):
                        questions_solved += 1
                        logger.info(f"Решен вопрос {questions_solved} в тесте: {test_title}")
                        time.sleep(self.test_delay)
                    else:
                        logger.warning("Не удалось отправить ответ")
                        break
                else:
                    logger.warning("Не удалось выбрать ответ")
                    break
            
            logger.info(f"Решено вопросов в тесте '{test_title}': {questions_solved}")
            return questions_solved > 0
            
        except Exception as e:
            logger.error(f"Ошибка при решении теста через ИИ: {e}")
            return False

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

    def process_tests(self):
        try:
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.type_bt, div.type_bw")
                )
            )

            tests_processed = 0
            consecutive_failures = 0
            max_consecutive_failures = 10

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

                            if (
                                "sttop_iconl_yet.gif" in src
                                or "sttop_iconl_notachieve.gif" in src
                            ):
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

                                            # Решение теста через ИИ
                                            if self.solve_test_with_ai(test_title):
                                                logger.info(
                                                    f"Тест {tests_processed} успешно решен через ИИ: {test_title}"
                                                )
                                            else:
                                                logger.warning(
                                                    f"Не удалось полностью решить тест {tests_processed}: {test_title}"
                                                )

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
                                    else:
                                        logger.warning(
                                            f"Не удалось открыть тест {tests_processed}: {test_title}"
                                        )
                                        tests_processed -= 1

                                break

                            else:
                                logger.debug(
                                    f"Тест уже завершен, пропускаем: {test_title}"
                                )
                                continue

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
                    logger.error(f"Ошибка при поиске тестов: {e}")
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(
                            "Критическое количество ошибок. Прекращение обработки."
                        )
                        break
                    time.sleep(5)
                    continue

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
            processed_count = self.process_tests()
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

            for subject_index, subject_name in enumerate(subject_names):
                is_first = subject_index == 0
                processed_count = self.process_subject(subject_name, is_first)
                total_processed += processed_count

                if subject_index == len(subject_names) - 1:
                    logger.info("Все предметы обработаны")

            if self.mode == "video":
                logger.info(f"Общее количество просмотренных видео: {total_processed}")
            elif self.mode == "test":
                logger.info(f"Общее количество обработанных тестов: {total_processed}")

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