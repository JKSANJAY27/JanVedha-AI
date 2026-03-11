import requests

r1 = requests.post('http://127.0.0.1:8000/api/auth/login', data={'username': 'je.d10@janvedha.ai', 'password': 'Password123'})
print("Login HTTP:", r1.status_code)
if r1.status_code == 200:
    token = r1.json()['access_token']
    r2 = requests.get('http://127.0.0.1:8000/api/officer/tickets?limit=100', headers={'Authorization': 'Bearer ' + token})
    print("Tickets HTTP:", r2.status_code)
    try:
        tickets = r2.json()
        print("Tickets JSON length:", len(tickets))
        if tickets:
            print("Priority label:", tickets[0].get('priority_label'))
            print("Dept ID:", tickets[0].get('dept_id'))
    except Exception as e:
        print("Failed to parse JSON", e)

r3 = requests.post('http://127.0.0.1:8000/api/auth/login', data={'username': 'je.d01@janvedha.ai', 'password': 'Password123'})
print("Login D01 HTTP:", r3.status_code)
if r3.status_code == 200:
    token = r3.json()['access_token']
    r4 = requests.get('http://127.0.0.1:8000/api/officer/tickets?limit=100', headers={'Authorization': 'Bearer ' + token})
    print("D01 Tickets length:", len(r4.json()))

