import threading
import sys
import os
import boto3
import loguru
import sqlalchemy
import sqlalchemy.ext.automap
import sqlalchemy.orm
import sqlalchemy.schema
import time
import json
from datetime import datetime
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

from threading import Thread
import zmq

cpu_serial = "0000000000000000"

f = open('/proc/cpuinfo', 'r')
for line in f:
	if line[0:6] == 'Serial':
		cpu_serial = line[10:26]
f.close()

# S3 setting
bucket_name = 'lab321-model'
# (V2)
#bucket_name = 'lab321-carview'
#folder_name = 'lab321-model/'
# model download target folder
object_folder = 'Models/Download/'
# model folder after successfully uploaded to PAG
model_current_folder = 'Models/CurrentModel/'
#model folder of history models
model_past_folder = 'Models/PastModels/'

# RDS setting
username = 'admin'     # RDS account
password = '12345678'     # RDS password
host = 'instai-web-rds.cvprqxu67qc8.us-east-1.rds.amazonaws.com'
RDS_port = '3306'         # RDS port
#database = 'carview'   # RDS name
database = 'myDB'
engine = sqlalchemy.create_engine(f'mysql+pymysql://{username}:{password}@{host}:{RDS_port}/{database}',echo=False)

# MQTT setting
#client_name = "test1"
#endpoint = "a1pxy4ej19lukk-ats.iot.us-east-1.amazonaws.com"
#MQTT_port = 8883
#pem = '/home/pi/Desktop/PAG_Project/MQTT/AmazonRootCA1.pem'
#private = '/home/pi/Desktop/PAG_Project/MQTT/c002ee5aa90852eebd52bd9bdfdd789cfd95a7a30b4e810c608fb385a763d7ce-private.pem.key'
#txt = '/home/pi/Desktop/PAG_Project/MQTT/c002ee5aa90852eebd52bd9bdfdd789cfd95a7a30b4e810c608fb385a763d7ce-certificate.pem.crt'

msg_update_hw_model_log = False
msg_device_id = ''
msg_success_model_name = ''

msg_start_request_model = False
msg_available_models = ''

msg_start_download = False
msg_internet_error = False
msg_hardware_unauth = False
msg_download_error = False
msg_download_model_name = ''

progress = 0.0

msg_terminate_program = False

# When client connect to service and get reponds
#def customCallback(client, userdata, message):
#	print("Callback came...")
#	b = message.payload
#	print(b)
#	y = json.loads(str(b, encoding = "UTF-8"))
#	print(y["message"]["status"])
#	if y["message"]["status"]["updateState"] == 1:
#		model = y["message"]["status"]["model"]
#		version = y["message"]["status"]["version"]
#		print(1)
#		download(model, version)
#	else:
#		print(0)

def GetKeysFromRDS():
	empty_lst = []
	session = None

	global msg_internet_error

	#while True:
	try:
		# get RDS data
		metadata = sqlalchemy.schema.MetaData(engine)
		# auto map RDS data
		automap = sqlalchemy.ext.automap.automap_base()
		automap.prepare(engine, reflect=True)

		# ORM connect 
		session = sqlalchemy.orm.Session(engine)

		sqlalchemy.Table('Devices', metadata, autoload=True)
		
		# CarNumber list
		#CarNumber1 = automap.classes['CarNumber']			# RDS CarNumber table
		# (V2)
		Devices = automap.classes['Devices']
		empty_lst = []							# table empty

		loguru.logger.info('Filtering Table Devices')
		#res1 = session.query(CarNumber1).filter(CarNumber1.boardId == boardid).all()	# get this boardId's Table
		# (V2)
		Device_res = session.query(Devices).filter(Devices.serialNumber == cpu_serial).all()
		# get hostId
		device_id = []
		for device in Device_res:
			device_id = device.id
			accesskey = device.accessKey			# get accessKey
			secretkey = device.secretKey			# get secretKey
		
		if device_id == empty_lst :
			# boardId isn't in RDS
			session.rollback()
			loguru.logger.error('Hardware is not authorized')
			# close RDS connect
			session.close()
			return False, '', ''
		
		# close RDS connect
		session.close()
		return True, accesskey, secretkey
		
	except Exception as e:
		if session is not None:
			session.rollback()
			session.close()
		loguru.logger.error('Connect to RDS failed')
		loguru.logger.error(e)
		msg_internet_error = True
	
# AppendHWUpdateLogs would not be used in version 20230430
def AppendHwUpdateLogs(DeviceID, success_model_name):
	
	global progress
	global msg_internet_error
	global msg_hardware_unauth
	
	session = None
	empty_lst = [] # define empty list
	
	#while True:
	try:
		# get RDS data
		metadata = sqlalchemy.schema.MetaData(engine)
		# auto map RDS data
		automap = sqlalchemy.ext.automap.automap_base()
		automap.prepare(engine, reflect=True)

		# ORM connect 
		session = sqlalchemy.orm.Session(engine)
		
		# retrieve Devices table
		sqlalchemy.Table('Devices', metadata, autoload=True)
		Devices = automap.classes['Devices']
		
		loguru.logger.info('Filtering Table Devices')
		Devices_res = session.query(Devices).filter(Devices.serialNumber == cpu_serial).all()
		# get Device Id
		device_id = []
		for device in Devices_res:
			device_id = device.id
		if device_id == empty_lst:
			# boardId isn't in RDS
			session.rollback()
			loguru.logger.error('Hardware is not authorized')
			msg_hardware_unauth = True
			# close RDS connect
			session.close()
			#break
		else:
			# look up Devices table and find the ID
			loguru.logger.info('Filtering Table Devices')
			sqlalchemy.Table('Devices', metadata, autoload=True)
			Devices = automap.classes['Devices']
			Devices_res = session.query(Devices).filter(Devices.deviceId == DeviceID, Devices.HostId == device_id).all()
			# get Device Id
			device_id = []
			for device in Devices_res:
				device_id = device.id
			
			if device_id == empty_lst:
				loguru.logger.error('Device could not be found')
				#break
			else:
				# get current time
				current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
				
				sqlalchemy.Table('HwUpdateLogs', metadata, autoload=True)
				Log = automap.classes['HwUpdateLogs']
				
				try:
					new_log = Log()
					new_log.created_at = current_time
					new_log.updated_at = current_time
					new_log.DeviceId = device_id
					new_log.modelName = success_model_name
					
					# save into the table
					session.add(new_log)
					session.commit()
					session.close()
					loguru.logger.info('HwUpdateLog create succeeded')
					progress = 100.0
					
				except Exception as e:
					if session is not None:
						session.rollback()
						session.close()
					loguru.logger.error('HwUpdateLog create failed')
					loguru.logger.error(e)
					msg_internet_error = True
			
	except Exception as e:
		loguru.logger.error('Access RDS Failed while logging HwUpdateLog')
		loguru.logger.error('Try to log again')
		loguru.logger.error(e)
		msg_internet_error = True
			

def GetAvailableModelName():

	# get RDS data
	#metadata = sqlalchemy.schema.MetaData(engine)
	# auto map RDS data
	#automap = sqlalchemy.ext.automap.automap_base()
	#automap.prepare(engine, reflect=True)

	# ORM connect 
	#session = sqlalchemy.orm.Session(engine)
	
	#sqlalchemy.Table('Models', metadata, autoload=True)
	
	# Model list
	#modelTable = automap.classes['Models']

	#loguru.logger.info('Get RDS data with filter')
	#modelList = []
	#modelList = session.query(modelTable).all()
	# get modelName and version
	#for model in modelList:
	#	print(f"model name: {model.modelName}, version: {model.modelVersion}")
	
	# close RDS connect
	#session.close()
	
	global msg_internet_error
	global msg_start_request_model
	global msg_hardware_unauth
	global progress
			
	hwAuth, accesskey, secretkey = GetKeysFromRDS()
	if hwAuth:
		s3 = boto3.client('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
			aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), 
			region_name=os.getenv('AWS_S3_REGION_NAME', 'us-east-1'))
	
		try:
			# get available model name from S3 bucket
			response = s3.list_objects_v2(Bucket=bucket_name)
			#response = s3.list_objects_v2(Bucket=bucket_name, Prefix=folder_name)
			files = response.get("Contents")
			
			modelList = []
			for file in files:
				modelList.append(file['Key'])
			# remove folder name
			#modelList.remove(folder_name)
			
			global msg_available_models
			for model in modelList:
				# get rid of folder name
				#model = model.replace(folder_name, '')
				msg_available_models += f"{model};"
				
			print(f"Available Models: {msg_available_models}")
		
		except Exception as e:
			msg_start_request_model = False
			msg_internet_error = True
			print("Request Model Failed")
			print(e)
	else:
		msg_start_request_model = False
		msg_hardware_unauth = True
		print("Hardware not authorized")
	
	# finish the process
	progress = 100.0


def download(model_name):
	#CNNFilt_20210223_PDFD_BW_400K.bin #CNNFilt_20211111_PDFD_BW.bin 			
	#0615CNNFilt_pad_CNNInit.bin #0719CNNFilt_pad_CNNInit.bin	
	#model_name = '0719CNNFilt_pad_CNNInit.bin'
	#model_name = '0615CNNFilt_pad_CNNInit.bin'
	#model_name = 'CNNFilt_20211111_PDFD_BW.bin'
	#model_name = 'CNNFilt_20210223_PDFD_BW_400K.bin'

	global progress
	global msg_internet_error
	global msg_hardware_unauth
	global msg_download_error
	global msg_start_download

	#file_name = folder_name + model_name
	file_name = model_name		
	object_name = object_folder + model_name

	hwAuth, accesskey, secretkey = GetKeysFromRDS()
	if hwAuth:
		s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
			aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), 
			region_name=os.getenv('AWS_S3_REGION_NAME', 'us-east-1'))
		try:
			object1 = s3.Object(bucket_name, file_name)
			size = object1.content_length
			# S3 Download File
			object1.download_file(object_name, Callback = ProgressPercentage(object_name, size))
			progress = 100.0
			print("Download Success")
        
			# move the current PAG model to history folder
			os.system(f"mv {model_current_folder}*.* {model_past_folder}")
			
			# upload the model to PAG7681
#			context = zmq.Context()
#			#  Socket to talk to server
#			print("Connecting to ZeroMQ server...")
#			socket = context.socket(zmq.REQ)
#			socket.connect("tcp://localhost:5555")
			#send the command to PAG Program
#			socket.send_string(f"update_model;{object_name}")
#			message = socket.recv()
#			print(f"Received: {message}")
			# request for the uploading progress every 1 second
#			while True:
#				socket.send_string("progress?")
#				message = socket.recv().decode()
#				print(f"Received: {message}")
#				if message == "Finish!":
					# move the downloaded model to current model folder
#					os.system(f"mv {object_name} {model_current_folder}")
#					break
#				time.sleep(1)
				
#			socket.close()
            
			
		except Exception as e:
			msg_download_error = True
			msg_start_download = False
			print("Download Failed")
			print(e)
	else:
		msg_download_error = False
		msg_hardware_unauth = True
		msg_start_download = False
		print("Hardware not authorized")


class ProgressPercentage(object):
	def __init__(self, filename, size):
		self._filename = filename
		self._size = size
		self._seen_so_far = 0
		self._lock = threading.Lock()

	def __call__(self, bytes_amount):
		# To simplify we'll assume this is hooked up
		# to a single filename.
		with self._lock:
			self._seen_so_far += bytes_amount
			global progress
			progress = (self._seen_so_far / self._size) * 100.0
			sys.stdout.write("\r%s  %s / %s  (%.2f%%)" % (
				self._filename, self._seen_so_far, self._size, progress))
			
			if progress >= 100.0:
				print()
			else:
				sys.stdout.flush()


# Connect setting
# Initialize client
#client = AWSIoTMQTTClient(client_name)
#client.configureEndpoint(endpoint, MQTT_port)
#client.configureCredentials(pem, private, txt)
# client.configureIAMCredentials(accessKey, secretKey)

# Starting connect
#client.connect()
#print("Client Connected")

# Subscribe
#client.subscribe(boardid, 1, customCallback)
#print('waiting for the callback. Click to conntinue...')

# Unsubscribe
#x = input()
#client.unsubscribe(boardid)
#print("Client unsubscribed")

# Disconnect
#client.disconnect()
#print("Client Disconnected")

def Thread_ZeroMQ():
	# initialize ZeroMQ Server
	context = zmq.Context()
	socket = context.socket(zmq.REP)
	socket.bind("tcp://*:2000")
	
	while True:
		recv_msg = socket.recv().decode('utf-8')
		
		#print(f"Received request: {recv_msg}")
		# split the message with ;
		recv_splits = recv_msg.split(';')
		
		# initialize messages
		global msg_available_models
		global progress
		global msg_hardware_unauth
		global msg_internet_error
		global msg_download_error
		global msg_device_id
		global msg_success_model_name
		global msg_update_hw_model_log
		
		global msg_terminate_program
		
		response_str = 'Invalid Command!'
		
		if msg_terminate_program == True:
			break
		
		elif recv_splits[0] == 'TERMINATE':
			socket.send('Exit Model Manager'.encode())
			msg_terminate_program = True
			break
			
		elif recv_splits[0] == 'get_available_model':
			msg_available_models = ""
			progress = 0.0
			msg_internet_error = False
			msg_download_error = False
			msg_hardware_unauth = False
			
			global msg_start_request_model
			msg_start_request_model = True
			
			response_str = 'OK'
			print("Requesting available models")
			
		elif recv_splits[0] == 'available_model?':
			response_str = msg_available_models
		
		elif recv_splits[0] == 'download':
			progress = 0.0
			msg_internet_error = False
			msg_download_error = False
			msg_hardware_unauth = False
			
			global msg_start_download
			if msg_start_download == True:
				response_str = 'Downloading ongoing'
			else:
				global msg_download_model_name
				msg_download_model_name = recv_splits[1]
				
				msg_start_download = True
				response_str = 'OK'
				print(f"Downloading model {msg_download_model_name}")
				
		elif recv_splits[0] == 'progress?':
			if msg_internet_error == True:
				response_str = 'Network Failed!'
			elif msg_download_error == True:
				response_str = 'Model Download Failed!'
			elif msg_hardware_unauth == True:
				response_str = 'Device is not Authorized!'
			elif progress == 0.0:
				response_str = 'Requesting Permission...'
			elif progress == 100.0:
				response_str = 'Done!'
			else:
				response_str = 'Downloading...; ' + ("%.2f" % progress) + '%'
		
		elif recv_splits[0] == 'append_hw_log':
			progress = 0.0
			msg_internet_error = False
			msg_download_error = False
			msg_hardware_unauth = False
			
			if len(recv_splits) != 3:
				response_str = 'Invalid Arguments!'
			else:
				msg_device_id = recv_splits[1]
				msg_success_model_name = recv_splits[2]
				msg_update_hw_model_log = True
				response_str = 'OK'
		
		socket.send(response_str.encode())


# create a thread for ZeroMQ message response
thread_zeroMQ = Thread(target=Thread_ZeroMQ, args=())
thread_zeroMQ.start()


# waiting for message to download the model file from S3 bucket
while True:
	
	if msg_terminate_program:
		break
		
	elif msg_start_request_model:
		GetAvailableModelName()
		msg_start_request_model = False
		
	elif msg_start_download:
		download(msg_download_model_name)
		msg_start_download = False
	
	elif msg_update_hw_model_log:
		AppendHwUpdateLogs(msg_device_id, msg_success_model_name)
		msg_update_hw_model_log = False

	time.sleep(0.5)
