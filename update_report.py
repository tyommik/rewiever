import  os
import pathlib
from collections import namedtuple
import csv
import datetime

INPUT = r'/home/ashibaev/Documents/ЗИП_АХТУНГ/Казань/Эфир/'


INPUT = pathlib.Path(INPUT)

Detection = namedtuple('Detection', 'pos, x1, y1, x2, y2, obj_class, precision')

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

#define ZIP_0 L"443746D1-23F3-4367-A99D-021171D8E006"
#define ZIP_6 L"780EF08B-FF15-483E-A4C4-0052585C7160"
#define ZIP_12 L"A5124A84-5049-480E-98C6-011679F448AC"
#define ZIP_16 L"C01258F9-54B2-4271-8D24-0578DAC65716"
#define ZIP_18 L"ACB5ACFE-4F6C-4AD7-8436-00746C5DCF91"

mapping = {0: '0+', 1: '6+', 2: '12+', 3: '16+', 4: '18+', 5: 'none'}

ZIP_PATTERN = {
    "0+": "443746D1-23F3-4367-A99D-021171D8E006",
    "6+": "780EF08B-FF15-483E-A4C4-0052585C7160",
    "12+": "A5124A84-5049-480E-98C6-011679F448AC",
    "16+": "C01258F9-54B2-4271-8D24-0578DAC65716",
    "18+": "ACB5ACFE-4F6C-4AD7-8436-00746C5DCF91"
}

csv_fieldnames = ['service_id', 'ResultSearchPatternID', 'time_start', 'time_stop', 'action', 'NewSearchPatternID', \
                  'BorderLeft', 'BorderTop', 'BorderWidth',	'BorderHeight', 'pattern_str', 'comment', 'local_time']

def getAllEvents(path):
    events = []
    for root, dirs, files in os.walk(path):
        for file in files:
            file = pathlib.Path(os.path.join(path, file))
            if file.suffix == '.log':
                anno = None
                log = file
                video = None
                if file.with_suffix('.mkv').exists():
                    video = file.with_suffix('.mkv')
                if file.with_suffix('.anno').exists():
                    anno = file.with_suffix('.anno')
                events.append((video, log, anno))
    return events

def process_event(event):
    def check_log_anno(log, anno):

        assert anno is not None
        with pathlib.Path.open(log, 'r') as log_f, pathlib.Path.open(anno, 'r') as anno_f:
            log_lines = [line.strip() for line in log_f.readlines()]
            anno_lines = [line.strip() for line in anno_f.readlines()]

            if log_lines == anno_lines:
                return True
            return False

    def annoIsEmpty(anno):
        anno_lines = []
        with pathlib.Path.open(anno, 'r') as anno_f:
            for line in anno_f.readlines():
                if line.startswith("#"):
                    continue
                anno_lines.append(line)
        if anno_lines:
            return False
        return True

    def getNewLabel(anno):
        labels = set()
        with pathlib.Path.open(anno, 'r') as anno_f:
            for line in anno_f.readlines():
                line = line.strip()
                if line.startswith("#"):
                    continue
                pos, x1, y1, x2, y2, obj_class, precision = line.split(' ')
                obj_class = int(obj_class)
                labels.add(obj_class)

        if len(labels) > 1:
            raise ValueError (anno)
        l = [label for label in labels][0]
        t = mapping[l]
        return t

    def getNewRect(anno):
        labels = set()
        with pathlib.Path.open(anno, 'r') as anno_f:
            for line in anno_f.readlines():
                line = line.strip()
                if line.startswith("#"):
                    continue
                pos, x1, y1, x2, y2, obj_class, precision = map(int, line.split(' '))
                labels.add((x1, y1, x2, y2))

        if len(labels) > 1:
            raise ValueError (anno)
        l = [label for label in labels][0]
        x, y, w, h = l[0], l[1], l[2] - l[0], l[3] - l[1]
        return x, y, w, h

    video, log, anno = event

    # parse name of file
    name_args = log.stem.split('_')
    CityName, start_date, lstart_time, end_date, lend_time, pattern_id = name_args

    # local_time = datetime.datetime.strptime(date + ' ' + ltime, '%d.%m.%Y %H:%M:%S.%f') - datetime.timedelta(hours=cities[CityName])
    start_UTC = datetime.datetime.strptime(start_date + ' ' + lstart_time, '%d.%m.%Y %H:%M:%S.%f') - datetime.timedelta(
        hours=cities[CityName.replace('+', ' ')])
    end_UTC = datetime.datetime.strptime(end_date + ' ' + lend_time, '%d.%m.%Y %H:%M:%S.%f') - datetime.timedelta(
        hours=cities[CityName.replace('+', ' ')])

    default = {i: "" for i in csv_fieldnames}
    default['local_time'] = datetime.datetime.strptime(start_date + ' ' + lstart_time, '%d.%m.%Y %H:%M:%S.%f')

    #pattern_id =log.stem.rsplit('_')[-1]
    default['ResultSearchPatternID'] = pattern_id
    pattern_str = getNewLabel(log)
    default["pattern_str"] = pattern_str

    default["time_start"] = start_UTC
    default["time_stop"] = end_UTC

    if video is None:
        default['comment'] = "CHECK_BY_HANDS"
        default['action'] = "VALID"
    else:
        if anno is None:
            default['comment'] = "CHECK_BY_HANDS"
            #default['action'] = "VALID"
            # лучше удалить
            default['action'] = "DELETE"
        else:

            # если аннотация пустая, т.е. ЛОЖНЯК
            if annoIsEmpty(anno):
                default["action"] = "DELETE"
            else:
                res = check_log_anno(log, anno)
                if res:
                    # если лог и аннотиция совпали, то VALID
                    default["action"] = "VALID"
                else:
                    # если не совпали - UPDATE
                    default["action"] = "UPDATE"
                    try:
                        default["NewSearchPatternID"] = ZIP_PATTERN[getNewLabel(anno)]
                    except:
                        a = getNewLabel(anno)
                        print()
                    x, y, w, h = getNewRect(anno)
                    default["BorderLeft"] = x
                    default["BorderTop"] = y
                    default["BorderWidth"] = w
                    default["BorderHeight"] = h
    return default

if __name__ == '__main__':
    events = sorted(getAllEvents(INPUT / 'video'), key=lambda x: str(x[1]))
    with pathlib.Path.open(INPUT / 'report.csv', 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_fieldnames)

        writer.writeheader()

        for event in events:
            result = process_event(event)
            writer.writerow(result)


