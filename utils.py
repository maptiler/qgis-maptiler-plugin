import urllib.request
import urllib.error

from qgis.PyQt.QtWidgets import QMessageBox


def validate_key(apikey='') -> bool:
    testurl = 'https://api.maptiler.com/maps/basic/style.json?key='
    try:
        response = urllib.request.urlopen(testurl + apikey)
        print(response.status)
        return True
    except urllib.error.HTTPError as e:
        print(e.code, e.msg)
        return False


def is_in_darkmode(threshold=383):
    """detect the Qt in Darkmode or not 

    This function has a dependancy on PyQt, QMessageBox.
    Although Qt has no API to detect running in Darkmode or not,
    it is able to get RGB value of widgets, including UI parts of them.
    This function detect Darkmode by evaluating a sum of RGB value of the widget with threshold.

    Args:
        threshold (int, optional): a sum of RGB value (each 0-255, sum 0-765). Default to 383, is just median.
    Returns:
        bool: True means in Darkmode, False in not.
    """
    # generate empty QMessageBox to detect
    # generated widgets has default color palette in the OS
    empty_mbox = QMessageBox()

    # get a background color of the widget
    red = empty_mbox.palette().window().color().red()
    green = empty_mbox.palette().window().color().green()
    blue = empty_mbox.palette().window().color().blue()

    sum_rgb_value = red + green + blue
    return sum_rgb_value < threshold


if __name__ == "__main__":
    validate_key('')
