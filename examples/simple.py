import ncis
ncis.install()
import time

var = 0
while True:
    var += 1
    print("var is {}".format(var))
    time.sleep(0.5)
    if var % 10 == 0:
        try:
            raise Exception("Oh noes!")
        except Exception as e:
            import traceback; traceback.print_exc()
