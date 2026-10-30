import csv

def g(path, field):
    with open(path, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return sorted(set(r.get(field, '') for r in rows if r.get(field, '')))

print('operator_job:', g('runtime/data/recorders.csv', 'operator_job'))
print('gender:', g('runtime/data/recorders.csv', 'gender'))
print('handedness:', g('runtime/data/recorders.csv', 'handedness'))
print('gloves:', g('runtime/data/recorders.csv', 'gloves'))
print('workforce_type:', g('runtime/data/recorders.csv', 'workforce_type'))
print('operator_consent:', g('runtime/data/recorders.csv', 'operator_consent'))
print('difficulty:', g('runtime/data/tasks.csv', 'difficulty'))
print('business_type:', g('runtime/data/tasks.csv', 'business_type'))
print('environment:', g('runtime/data/environments.csv', 'environment'))
print('facility_venue:', g('runtime/data/environments.csv', 'facility_venue'))
print('scene:', g('runtime/data/environments.csv', 'scene'))
print('capture_mode:', g('runtime/data/sd_cards.csv', 'capture_mode'))
