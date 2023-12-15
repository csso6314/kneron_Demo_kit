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
from datetime import datetime
from boto3.s3.transfer import TransferConfig
#from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

output_identifier = "[OUTPUT_RES]::"
temp_folder = "../kneron_plus/res/models/KL520/tiny_yolo_v3/"
pc_hostname = os.popen('hostname').read().strip()

# inspect whether the folder download exists
if not os.path.exists(temp_folder):
	os.makedirs(temp_folder)

# S3 setting: bucket name and folder name (also known as "key" or "prefix")
bucket_name = 'lab321-model'
#bucket_prefix = 'pixart'
bucket_prefix = 'kneron'

# RDS setting
username = 'admin'     # RDS account
password = 'instai76666'     # RDS password
host = 'instai-rds.cwxva4x4deuv.us-east-1.rds.amazonaws.com'
RDS_port = '3306'         # RDS port
#database = 'carview'   # RDS name
database = 'myDB'
engine = sqlalchemy.create_engine(f'mysql+pymysql://{username}:{password}@{host}:{RDS_port}/{database}',echo=False)

config = TransferConfig(multipart_threshold = 1024*10,		# more than 10MB
			max_concurrency = 10,			
			multipart_chunksize = 1024*10,		# multipart size
			use_threads = True)			# S3 multi thread transmit

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
		Device_res = session.query(Devices).filter(Devices.serialNumber == pc_hostname).all()
		# get hostId
		device_id = []
		for device in Device_res:
			device_id = device.id
			accesskey = device.accessKey			# get accessKey
			secretkey = device.secretKey			# get secretKey
		
		if device_id == empty_lst :
			# boardId isn't in RDS
			session.rollback()
			loguru.logger.error('PC is not authorized')
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
		Devices_res = session.query(Devices).filter(Devices.serialNumber == pc_hostname).all()
		# get Device Id
		device_id = []
		for device in Devices_res:
			device_id = device.id
		if device_id == empty_lst:
			# boardId isn't in RDS
			session.rollback()
			loguru.logger.error('PC is not authorized')
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
	
	hwAuth, accesskey, secretkey = GetKeysFromRDS()
	if hwAuth:
		s3 = boto3.client('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
			aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), 
			region_name=os.getenv('AWS_S3_REGION_NAME', 'us-east-1'))
	
		try:
			# get available model name from S3 bucket
			response = s3.list_objects_v2(Bucket=bucket_name, Prefix=bucket_prefix)
			files = response.get("Contents")
			
			modelList = []
			for file in files:
				modelList.append(file['Key'])
			# remove folder name
			#modelList.remove(folder_name)
			
			msg_available_models = ""
			for model in modelList:
				# get rid of folder name
				#model = model.replace(folder_name, '')
				if ".nef" in model:
					model = model.replace(".nef", "")
					msg_available_models += f"{model};"
				
			print(f"{output_identifier}{msg_available_models}")
		
		except Exception as e:
			print(f"{output_identifier}Could not Reach Internet!")
			print(e)
	else:
		print(f"{output_identifier}PC is not Authorized!")


def download(download_filename):
	#file_name = folder_name + model_name
	file_name = download_filename
	object_name = temp_folder + download_filename

	hwAuth, accesskey, secretkey = GetKeysFromRDS()
	if hwAuth:
		s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
			aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), 
			region_name=os.getenv('AWS_S3_REGION_NAME', 'us-east-1'))
		try:
			object1 = s3.Object(bucket_name, bucket_prefix + "/" + file_name)
			size = object1.content_length
			# S3 Download File
			object1.download_file(object_name, Callback = Download_ProgressPercentage(object_name, size))
			print(f"{output_identifier}Success!")
            
		except Exception as e:
			print(f"{output_identifier}File not Exist!")
			print(e)
	else:
		print(f"{output_identifier}PC is not Authorized!")

def upload(upload_filename):
	hwAuth, accesskey, secretkey = GetKeysFromRDS()
	object_name = temp_folder + upload_filename
	if hwAuth:
		try:
			loguru.logger.info('Accessing S3')
			# s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
			# 				aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), endpoint_url='https://lab321-carview.s3-accelerate.amazonaws.com')
			s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),
				aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), 
				region_name=os.getenv('AWS_S3_REGION_NAME', 'us-east-1'))
			# s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),
			# 	aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), 
			# 	endpoint_url='https://lab321-model.s3.amazonaws.com/')
			s3.Object(bucket_name, bucket_prefix + "/" + upload_filename).upload_file(object_name, ExtraArgs = {'ContentType':'*/*'},
								Config = config, Callback = Upload_ProgressPercentage(object_name))
			print(f"{output_identifier}Success!")
		except Exception as e:
			print(f"{output_identifier}File not Exist!")
			print(e)
	else:
		print(f"{output_identifier}PC is not Authorized!")

class Download_ProgressPercentage(object):
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
			#global progress
			progress = (self._seen_so_far / self._size) * 100.0
			sys.stdout.write("\r%s  %s / %s  (%.2f%%)" % (
				self._filename, self._seen_so_far, self._size, progress))
			
			if progress >= 100.0:
				print()
			else:
				sys.stdout.flush()

class Upload_ProgressPercentage(object):
	def __init__(self, filename):
		self._filename = filename
		self._size = float(os.path.getsize(filename))
		self._seen_so_far = 0
		self._lock = threading.Lock()

	def __call__(self, bytes_amount):
		# To simplify we'll assume this is hooked up
		# to a single filename.
		with self._lock:
			self._seen_so_far += bytes_amount
			percentage = (self._seen_so_far / self._size) * 100
			sys.stdout.write("\r%s  %s / %s  (%.2f%%)" % (
				self._filename, self._seen_so_far, self._size,
				percentage))
			if percentage >= 100.0:
				print()
			else:
				sys.stdout.flush()

args = sys.argv[1:]
if len(args) == 0:
	print("Error Command Format! [Command] [Parameters...]")
	exit(0)

command = ""
parameter = ""

if len(args) >= 1:
	command = args[0]
	if len(args) >= 2:
		parameter = args[1]
	
if command == "hostname?":
	print(f"{output_identifier}{pc_hostname}")

elif command == "available_model?":
	GetAvailableModelName()
elif command == "download":
	download(parameter)
elif command == "upload":
	upload(parameter)
# download(msg_download_model_name)
