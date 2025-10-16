# фалй должен называться config.py
# https://googlechromelabs.github.io/chrome-for-testing/ - скачать ласт версию chrome driver


# заменяйте на свои учетные данные
login = "your_login_here"
password = "your_password_here"





# вот тут массив предметов

subject_names = [
    "subject1",        
    "subject2",       
    "subject3",  
    "subject4" 
]




# Режим работы: 'video' для просмотра видео, 'test' для решения тестов

mode = 'video'  
# mode = 'test'






# пока скрипт решения тестов работает только с google gemini 2.0, если у вас есть другие api (лучше) можете в class aitestsolver init поменять url на свой и изменить структуру запроса в функции solvequestion
AI_api_key = 'your_ai_api_key'




# если True — chrome работает в фоновом режиме без GUI без отображения окна браузера, а если False показывается
HEADLESS = True # False11