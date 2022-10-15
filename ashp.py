import yaml

with open("ashp.yml", "r") as f:
	ashp_list = yaml.load(f)

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

def ASHP_list():
	print("_________________")
	print("ASHP's available:")
	print("-"  +next(iter(ashp_list)) )
	print("_________________")

ashp_settings = {}
byte_data = {}
bin_data = {}

def bin_assign(binary_arr, start, length, value, endianess="msb"):
	for i in range(length-1, -1, -1):
		if endianess == "msb":
			binary_arr[start+(length-1-i)] = (value & (1 << i)) >> i
		elif endianess == "lsb":
			binary_arr[start+i] = (value & (1 << i)) >> i

def setting_assign(binary_arr, ashp, setting, value=None):
	if (not setting in ashp):
		print("? NOTICE:	no '" + setting + "' possible with this ASHP, value omitted")
		return

	if (value != None):
		print("> INFO:	Setting " + setting + " to " + str(value) + "...")
	else:
		print("> INFO:	Setting " + setting + "....")
	if (setting == "temperature"):
		realvalue = int(value)-ashp[setting]['offset']
	elif (setting == "fanspeed"):
		if (value != "auto"):
			stepvalue = min(ashp[setting]['values'], key=lambda x:abs(safe_cast(x, int, -1000) - value))
			realvalue = ashp[setting]['values'][stepvalue]
		else:
			realvalue = ashp[setting]['values']['auto']
	elif (setting == "mode"):
		realvalue = ashp[setting]['values'][value]
	elif (setting == "swing-vertical" or setting == "swing-horizontal"):
		if (value != "auto"):
			stepvalue = min(ashp[setting]['values'], key=lambda x:abs(safe_cast(x, int, -1000) - value))
			realvalue = ashp[setting]['values'][stepvalue]
		else:
			realvalue = ashp[setting]['values']['auto']
	elif (setting == "onoff"):
		realvalue = ashp[setting]['onoff'][value]
	elif (setting == "checksum"):	
		checksum = 0;
		if (ashp[setting]['type'] == "byte-sum"):
			for i in range(int(ashp[setting]['start']/8),int(ashp[setting]['end']/8)):
				checksum = checksum + (binary_arr[(i*8)+0] << 7) + (binary_arr[(i*8)+1] << 6) + (binary_arr[(i*8)+2] << 5) + (binary_arr[(i*8)+3] << 4) + (binary_arr[(i*8)+4] << 3) + (binary_arr[(i*8)+5] << 2) + (binary_arr[(i*8)+6] << 1) + (binary_arr[(i*8)+7])
			if (ashp[setting]['constant'] < 0):
				checksum = ashp[setting]['constant'] - checksum
			else:
				checksum = checksum + ashp[setting]['constant']
		realvalue = checksum % 256
	if (value and 'stepvalue' in locals() and value != stepvalue):
		print("? NOTICE:"+setting + " changed automatically from " + str(value) + " to " + str(stepvalue))
	bin_assign(binary_arr, ashp[setting]['place'], ashp[setting]['length'], realvalue, ashp[setting]['endianess'])

def ASHP_setup(manufacturer, on_off=1, temperature=21.0, mode="heating", fanspeed=50, swing_vertical=50, swing_horizontal=50, puremode=0):
	cur_ashp = ashp_list[manufacturer]
	print("ASHP SETUP: " + manufacturer + "(" + str(cur_ashp['frequency']) + " Hz)")
	byte_data = cur_ashp['template']['data']
	cnt = 0
	bnr = 0;
	for i in range(len(byte_data)):
		for bit in range(7, -1, -1):
			bnr = (byte_data[i] & (1 << bit)) >> bit
			bin_data[cnt] = bnr
			cnt = cnt + 1

	setting_assign(bin_data, cur_ashp, 'temperature', temperature)
	setting_assign(bin_data, cur_ashp, 'mode', mode)
	setting_assign(bin_data, cur_ashp, 'fanspeed', fanspeed)
	setting_assign(bin_data, cur_ashp, 'swing-vertical', swing_vertical)
	setting_assign(bin_data, cur_ashp, 'swing-horizontal', swing_horizontal)
	setting_assign(bin_data, cur_ashp, 'puremode', puremode)
	setting_assign(bin_data, cur_ashp, 'onoff', on_off)
	setting_assign(bin_data, cur_ashp, 'checksum')

def ASHP_binary_to_byte(binary_arr, byte_d, hexstr):
	for i in range(0, len(bin_data), 8):
		byte_d[i/8] = (binary_arr[i+0] << 7) + (binary_arr[i+1] << 6) + (binary_arr[i+2] << 5) + (binary_arr[i+3] << 4) + (binary_arr[i+4] << 3) + (binary_arr[i+5] << 2) + (binary_arr[i+6] << 1) + (binary_arr[i+7])
		hexstr[i/8] = '0x{:02x}'.format(byte_d[i/8]);

def ASHP_full_code(commandlist, manufacturer):
	frames = ashp_list[manufacturer]['frames']
	cursor = 0
	newdict = {}
	dictcursor = 0
	for frame in frames:
		if 'databits' in frame:
			for i in range(cursor, cursor+int(frame['databits']/8)):
				#print str(cursor) + ":	" + str(commandlist[i])
				newdict[dictcursor] = "0x{:02d}".format(cursor) + ":	"+ str(commandlist[i])
				cursor = cursor + 1
				dictcursor = dictcursor + 1
		else:
			#print frame
			newdict[dictcursor] = frame
			dictcursor = dictcursor + 1
	return newdict

if __name__ == "__main__":
	# Creating Panasonic ASHP code with ON & 26*C target temperature
	ASHP_setup('panasonic',	
		1, #on/off
		26, #temperature
		'heating', #mode
		43, #fanspeed
		29, #swing vertical
		88, #swing horizontal
		1) # pure/clean/plasma/ion
	hxx = {}
	ASHP_binary_to_byte(bin_data, byte_data, hxx)
	hxx = ASHP_full_code(hxx, 'panasonic')

	for i in range(len(hxx)):
		print(str(hxx[i]))
