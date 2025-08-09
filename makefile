FQBN = arduino:avr:uno
PORT = /dev/ttyACM0
SKETCH = .

.PHONY: all compile upload monitor clean

all: compile

compile:
	arduino-cli compile --fqbn $(FQBN) $(SKETCH)

upload: compile
	arduino-cli upload -p $(PORT) --fqbn $(FQBN) $(SKETCH)

monitor:
	arduino-cli monitor -p $(PORT) -c baudrate=115200

clean:
	rm -rf build
