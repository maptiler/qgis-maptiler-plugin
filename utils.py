import urllib.request
import urllib.error

def validate_key(apikey='')->bool:
    testurl = 'https://api.maptiler.com/maps/basic/style.json?key='
    try:
        response = urllib.request.urlopen(testurl + apikey)
        print(response.status)
        return True
    except urllib.error.HTTPError as e:
        print(e.code, e.msg)
        return False

if __name__ == "__main__":
    validate_key('')