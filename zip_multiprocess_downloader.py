import csv
import re
import requests
import datetime
import os
import cv2
import json
import tqdm
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThreadPool, JoinableQueue
from itertools import product
import pathlib
import subprocess
import csv


from PIL import Image, ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

# SETTINGS
CSV_FILE = r'/home/ashibaev/Documents/ЗИП_АХТУНГ/Тольяти/РЕН-ТВ/source.csv'


def read_csv(csvfile):
    with open(csvfile, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=';')
        for row in reader:
            yield row

TEMP = pathlib.Path(CSV_FILE).parent
FPS = 25
read_csv_gen = read_csv(CSV_FILE)

cities = {
    "Воронеж": 3,
    "Иваново": 3,
    "Калуга": 3,
    "Кострома": 3,
    "Липецк": 3,
    "Орел": 3,
    "Рязань": 3,
    "Смоленск": 3,
    "Тамбов": 3,
    "Тверь": 3,
    "Тула": 3,
    "Ярославль": 3,
    "Архангельск": 3,
    "Великий Новгород": 3,
    "Вологда": 3,
    "Мурманск": 3,
    "Нарьян-Мар": 3,
    "Псков": 3,
    "Санкт-Петербург": 3,
    "Сыктывкар": 3,
    "Ижевск": 4,
    "Йошкар-Ола": 3,
    "Киров": 3,
    "Оренбург": 5,
    "Пенза": 3,
    "Саранск": 3,
    "Саратов (БПАС)": 4,
    "Ульяновск": 4,
    "Уфа": 5,
    "Чебоксары": 3,
    "Астрахань": 4,
    "Владикавказ": 3,
    "Волгоград": 4,
    "Грозный": 3,
    "Майкоп": 3,
    "Махачкала": 3,
    "Назрань": 3,
    "Нальчик": 3,
    "Черкесск": 3,
    "Элиста": 3,
    "Курган": 5,
    "Салехард": 5,
    "Тюмень": 5,
    "Ханты-Мансийск": 5,
    "Челябинск": 5,
    "Абакан SL01485": 7,
    "Горно-Алтайск": 7,
    "Иркутск": 8,
    "Кемерово": 7,
    "Красноярск SL01522": 7,
    "Кызыл SL01501": 7,
    "Новосибирск": 7,
    "Омск": 6,
    "Улан-Удэ": 8,
    "Чита": 9,
    "Анадырь": 12,
    "Биробиджан": 10,
    "Благовещенск": 9,
    "Магадан": 11,
    "Петропавловск-Камчатский": 12,
    "Южно-Сахалинск": 11,
    "Якутск": 9,
    "Петрозаводск": 3,
    "Калининград": 2,
    "Брянск": 3,
    "Курск": 3,
    "Белгород": 3,
    "Симферополь": 3,
    "Севастополь": 3,
    "Ростов-на-Дону": 3,
    "Краснодар": 3,
    "Ставрополь": 3,
    "Москва": 3,
    "Владимир": 3,
    "Нижний Новгород": 3,
    "Нижний Новгород (ПБПАС)": 3,
    "Казань": 3,
    "Самара": 4,
    "Пермь БПАС-1": 5,
    "Екатеринбург": 5,
    "Томск": 7,
    "Барнаул": 7,
    "Хабаровск": 10,
    "Находка": 10,
    "Владивосток": 10,
    "Самара (ПБПАС)": 4,
    "Москва (ПБПАС)": 3,
    "Альметьевск (ПБПАС-1)": 3,
    "Симферополь (ПБПАС)": 3,
    "Севастополь (ПБПАС)": 3,
    "Владимир PBPAS-2017-035": 3,
    "Старый Оскол": 3,
    "Ковров": 3,
    "Муром": 3,
    "Обнинск": 3,
    "Новомосковск": 3,
    "Рыбинск": 3,
    "Ногинск": 3,
    "Северодвинск": 3,
    "Череповец": 3,
    "Октябрьский": 5,
    "Нефтекамск": 5,
    "Арзамас": 3,
    "Орск": 5,
    "Березники": 5,
    "Набережные Челны": 3,
    "Таганрог": 3,
    "Сочи": 3,
    "Камышин": 4,
    "Пятигорск": 3,
    "Дербент": 3,
    "Каменск-Уральский": 5,
    "Нижний Тагил": 5,
    "Первоуральск": 5,
    "Златоуст": 5,
    "Ноябрьск": 5,
    "Новый Уренгой": 5,
    "Сургут": 5,
    "Комсомольск-на-Амуре": 10,
    "Уссурийск (КБПАС)": 10,
    "Керчь": 3,
    "Евпатория": 3,
    "Феодосия": 3,
    "Ялта": 3,
    "Белгород (ПБПАС)": 3,
    "Брянск (ПБПАС)": 3,
    "Воронеж (ПБПАС)": 3,
    "Москва PBPAS-2017-033": 3,
    "Москва PBPAS-2017-034": 3,
    "Москва PBPAS-2017-036": 3,
    "Рязань (ПБПАС)": 3,
    "Смоленск (ПБПАС)": 3,
    "Тверь (ПБПАС)": 3,
    "Тула (ПБПАС)": 3,
    "Архангельск (ПБПАС)": 3,
    "Вологда (ПБПАС)": 3,
    "Калининград (ПБПАС)": 2,
    "Мурманск (ПБПАС)": 3,
    "Петрозаводск (ПБПАС)": 3,
    "Сыктывкар (ПБПАС)": 3,
    "Санкт-Петербург (ПБПАС)": 3,
    "Нижний Новгород PBPAS-2017-037": 3,
    "Нижний Новгород PBPAS-2017-040": 3,
    "Бугуруслан (ПБПАС)": 5,
    "Бузулук (ПБПАС)": 5,
    "Чайковский (ПБПАС)": 5,
    "Казань (ПБПАС-3)": 3,
    "Сызрань PBPAS-2017-039": 4,
    "Энгельс (ПБПАС)": 4,
    "Ульяновск (ПБПАС)": 4,
    "Чебоксары (ПБПАС)": 3,
    "Астрахань (ПБПАС)": 4,
    "Волгоград (ПБПАС)": 4,
    "Новороссийск PBPAS-2017-015": 3,
    "Краснодар PBPAS-2017-016": 3,
    "Дербент  PBPAS-2017-031": 3,
    "Махачкала PBPAS-2017-032": 3,
    "Черкесск (ПБПАС)": 3,
    "Цимлянск (ПБПАС)": 3,
    "Ставрополь PBPAS-2017-013": 3,
    "Ставрополь PBPAS-2017-018": 3,
    "Курган (ПБПАС)": 5,
    "Тюмень (ПБПАС)": 5,
    "Челябинск (ПБПАС)": 5,
    "Рубцовск (ПБПАС)": 7,
    "Иркутск (ПБПАС-047)": 8,
    "Иркутск (ПБПАС-043)": 8,
    "Кемерово (ПБПАС)": 7,
    "Абакан PBPAS-2017-046": 7,
    "Красноярск PBPAS-2017-048": 7,
    "Красноярск PBPAS-2017-049": 7,
    "Новосибирск (ПБПАС)": 7,
    "Омск (ПБПАС)": 6,
    "Томск (ПБПАС)": 7,
    "Благовещенск (ПБПАС)": 9,
    "Петропавловск-Камчатский (ПБПАС)": 12,
    "Магадан (ПБПАС)": 11,
    "Якутск (ПБПАС)": 9,
    "БПЭС Смоленск КТСРК-1": 3,
    "БПЭС Смоленск КТСРК-2": 3,
    "БПЭС Смоленск ККЗК-1": 3,
    "БПЭС Смоленск ККЗК-2": 3,
    "БПЭС Белгород КТСРК-1": 3,
    "БПЭС Белгород КТСРК-2": 3,
    "БПЭС Белгород ККЗК-1": 3,
    "БПЭС Белгород ККЗК-2": 3,
    "БПЭС Хабаровск КТСРК-1": 3,
    "БПЭС Хабаровск КТСРК-2": 3,
    "БПЭС п. Новый (Новосибирская область) ККЗК-1": 7,
    "БПЭС п. Новый (Новосибирская область) ККЗК-2": 7,
    "Ангарск (КБПАС-5)": 8,
    "Братск (КБПАС-5)": 8,
    "Новокузнецк (КБПАС-5)": 7,
    "Норильск (КБПАС-5)": 7,
    "Магнитогорск (КБПАС-5)": 5,
    "Балаково (КБПАС-5)": 4,
    "Нижнекамск (КБПАС-5)": 3,
    "Тольятти (КБПАС-5)": 4,
    "Армавир (КБПАС-5)": 3,
    "Новороссийск (КБПАС-5)": 3,
    "Шахты (КБПАС-5)": 3,
    "Сызрань": 4,
    "Альметьевск": 3,
    "Ачинск": 7,
    "Кисловодск": 3,
    "Находка (КБПАС)": 10,
    "Невинномысск": 3,
    "Новочеркасск": 3,
    "Рубцовск": 7,
    "Салават": 5,
    "Хасавюрт": 3,
    "Цимлянск": 3,
    "Артём": 10,
    "Железногорск": 3,
    "Серов": 5,
    "Stream Labs": 3,
    "SL-EKB": 5,
}

def create_anno(anno_path, params: dict):
    x1, y1, x2, y2 = params["left"], params["top"], params["left"] + params["width"], params["top"] + params["height"]
    obj_class = params["obj_class"]
    duration = params["duration"]
    gap = params["gap"]
    lines = []
    # for frame in range(gap, gap + int(duration * FPS)):
    for frame in range(0, gap + int(duration * FPS)):
        # pos, x1, y1, x2, y2, obj_class, precision = line.split(' ')
        lines.append(f'{frame} {x1} {y1} {x2} {y2} {obj_class} 0\n')
    with pathlib.Path.open(anno_path, 'w') as inf:
        inf.write("# start\n")
        for line in lines:
            inf.write(line)
        inf.write("# end\n")
    return True


def convert_to_mkv(video_file):
    file = pathlib.Path(video_file)
    # ffmpeg -i <INPUT> -vcodec copy -ss 00:00:00 -force_key_frames 00:00:00 -map 0:0 -sn -map_metadata 0 <OUTPUT>
    args = f'ffmpeg -i {str(file)} -vcodec copy -ss 00:00:00 -force_key_frames 00:00:00 -map 0:0 -sn -map_metadata 0 {str(file.with_suffix(".mkv"))} -y'
    p = subprocess.run(args.split(' '))
    if p.returncode == 0:
        return True
    return False

def convert_to_mkv_mkvtoolnix(video_file):
    file = pathlib.Path(video_file)
    # /usr/bin/mkvmerge --output test.mkv --no-audio --language 0:und '(' test.ts ')'
    args = f"mkvmerge --output {str(file.with_suffix('.mkv'))} --no-audio --language 0:und " + f"{str(file)}"
    p = subprocess.run(args.split(' '))
    if p.returncode == 0:
        return True
    return False

def download_file(args):
    url, file = args
    try:
        r = requests.get(url, allow_redirects=True, timeout=5)
        r.raise_for_status()
    except Exception as err:
        print(f'{type(err).__name__} {str(err)}')
    else:
        with pathlib.Path.open(file, 'wb') as ouf:
            ouf.write(r.content)
            convert_to_mkv_mkvtoolnix(file)
        return True
    return False


mapping = {0: '0+', 1: '12+', 2: '16+', 3: '18+', 4: '6+', 5: 'none'}
reverse_mapping = {'0+': 0, '6+': 1, '12+': 2, '16+': 3, '18+': 4 }

START_ROW = 0
GAP = 5 * 25 # seconds * fps

if __name__ == '__main__':

    try:
        os.mkdir(os.path.join(TEMP, 'video'))
    except:
        pass

    url_list = []
    queue = JoinableQueue(8000)
    pool = ThreadPool(8)

    for idx, row in enumerate(tqdm.tqdm(read_csv_gen, position=0)):

        # if idx < START_ROW:
        #     continue

        GUID, \
        SearchPatternName, \
        start, \
        end, \
        BorderLeft, \
        BorderTop, \
        BorderWidth, \
        BorderHeight,\
        url, \
        SearchPatternID = row['ResultSearchPatternID'], \
              row['SearchPatternName'], \
              row['Start'], \
              row['End'], int(row['BorderLeft']), int(row['BorderTop']), int(row['BorderWidth']), int(row['BorderHeight']), row['URL'], row['SearchPatternID']

        name = row["NodeName"]
        timezone = cities[name]
        # parse time

        try:
            start = start[:-9]
            end = end[:-9]
            # starttime = datetime.datetime.strptime(start, '%m/%d/%y %H:%M %p')
            # endtime = datetime.datetime.strptime(end, '%m/%d/%y %H:%M %p')
            starttime = datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S.%f') - datetime.timedelta(hours=3)
            endtime = datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S.%f') - datetime.timedelta(hours=3)

            local_starttime = starttime + datetime.timedelta(hours=timezone)
            local_endtime = endtime + datetime.timedelta(hours=timezone)
        except Exception as err:
            print(f'{row}')
        else:
            duration = (endtime - starttime).total_seconds()

            match = re.findall(r'^(?P<zip>\+?\d{1,2}\+?)', SearchPatternName)
            pattern = match[0].replace('+', '') + '+' if match else None

            # if starttime < datetime.datetime.today().replace(hour=6, minute=0):
            #     continue

            video_file_name = f'{row["NodeName"].replace(" ", "+")}_{local_starttime.strftime("%d.%m.%Y_%H:%M:%S")}_{local_endtime.strftime("%d.%m.%Y_%H:%M:%S")}_{GUID}.ts'
            video_file = TEMP / 'video' / video_file_name

            anno_path = video_file.with_suffix('.log')
            create_anno(anno_path, {"top": BorderTop,
                         "left": BorderLeft,
                         "width": BorderWidth,
                         "height": BorderHeight,
                         "obj_class": reverse_mapping[pattern],
                         "duration": duration,
                         "gap": GAP
                         })

            if video_file.exists():
                print(f'{idx}: Video file exists. Skip!')
                continue

            url_list.append((url, video_file))

    result = pool.map(download_file, url_list)
    # close the pool and wait for the work to finish
    pool.close()
    pool.join()
    url_list.clear()

    print("############################################\n")
    print("\n")
    print("################# Г О Т О В О ###############\n")
    print("\n")
    print("######## ЗАПУСТИТЕ УТИЛИТУ РАЗМЕТКИ ########\n")
