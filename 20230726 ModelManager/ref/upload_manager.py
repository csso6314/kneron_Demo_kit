import time
import requests
import threading
import os
import boto3
import sys

# import datetime
import loguru
import sqlalchemy
import sqlalchemy.ext.automap
import sqlalchemy.orm
import sqlalchemy.schema
from boto3.s3.transfer import TransferConfig

# 20230430 append zeroMQ for feeding back uploading progress
from threading import Thread
import zmq

#process = subprocess.run(["hrut_socuid"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", timeout=1)	# X3 BoardID
#boardid = (process.stdout.split('\n')[0]).split(' ')[1]								# get BoardID

# initialize variables
cpu_serial = "0000000000000000"

f = open('/proc/cpuinfo', 'r')
for line in f:
	if line[0:6] == 'Serial':
		cpu_serial = line[10:26]
f.close()

#refresh_proj_name_program = 'refresh_project_name.py'
#refresh_proj_name_result = 'project_name.txt'
#project_name = ""

username = 'admin'     # RDS account
password = '12345678'     # RDS password
host = 'instai-web-rds.cvprqxu67qc8.us-east-1.rds.amazonaws.com'
port = '3306'         # RDS port
#database = 'carview'   # RDS name
database = 'myDB'     # version2
engine = sqlalchemy.create_engine(f'mysql+pymysql://{username}:{password}@{host}:{port}/{database}',echo=False)


config = TransferConfig(multipart_threshold = 1024*10,		# more than 10MB
			max_concurrency = 10,			
			multipart_chunksize = 1024*10,		# multipart size
			use_threads = True)			# S3 multi thread transmit

# global variables
msg_terminate_program = False
msg_upload_videos = False
msg_upload_pictures = False

msg_hardware_unauth = False
msg_network_failed = False

progress = 0.0

class SendFile():
	def __init__(self, s, address, upload, sucupload):
		self.s = s
		self.upload = upload									# data folder name
		self.dir = address + upload							# data folder path
		self.UploadSuccess = address + sucupload				# finish upload folder path
		self.allFileLise = os.listdir(self.dir)		# file list

	#def filename_append_project_name(self):
	#	for file in self.allFileLise:
	#		os.rename(f"{self.dir}{file}", f"{self.dir}{project_name}_{file}")

	def multipart_upload_boto3(self):
		global msg_hardware_unauth
		global msg_network_failed
		global progress

		try:
			empty_lst = []	# define empty table
			
			# get RDS data
			metadata = sqlalchemy.schema.MetaData(engine)
			# auto map RDS data
			automap = sqlalchemy.ext.automap.automap_base()
			automap.prepare(engine, reflect=True)

			# ORM connect 
			session = sqlalchemy.orm.Session(engine)

			# enter table Devices
			sqlalchemy.Table('Devices', metadata, autoload=True)
			
			# 0921 table name modification
			Devices = automap.classes['Devices']	# RDS Devices table

			loguru.logger.info('Filtering Table Devices')
			Device_res = []
			#res1 = session.query(CarNumber1).filter(CarNumber1.boardId == boardid).all()	# get this boardId's Table
			Device_res = session.query(Devices).filter(Devices.serialNumber == cpu_serial).all()	# (V2) get this boardId's Table
			# get Device Id
			device_id = []
			project_id = []
			for device in Device_res:
				device_id = device.id
				project_id = device.ProjectId
				accesskey = device.accessKey			# get accessKey
				secretkey = device.secretKey			# get secretKey
			
			if (device_id == empty_lst) or (project_id == empty_lst) :
				# boardId isn't in RDS
				session.rollback()
				loguru.logger.error('Hardware is not authorized')
				# close RDS connect
				session.close()

				# update the interface message
				msg_hardware_unauth = True
			else:
				loguru.logger.info('Accessing S3')
				s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
								aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), endpoint_url='https://lab321-carview.s3-accelerate.amazonaws.com')

				# refresh filename in directory
				self.allFileLise = sorted(os.listdir(self.dir))

				uploaded_file_counter = 0

				for file in self.allFileLise:
					list1 = file.split('_')				# filename split
					list2 = file.split('.')				# main filename split
					file_path = self.dir + file			# data path include filename
					key = file					# aws target path
					bucket_upload_folder = self.upload.split('/')[0] 
					eventtime = list1[2][0:4] + '-' + list1[2][4:6] + '-' + list1[2][6:8] + ' ' + list1[2][8:10] + ':' + list1[2][10:12] + ':' + list1[2][12:14]		# file event time
					
					# ORM connect
					loguru.logger.info('Filtering Table Data')
					sqlalchemy.Table('Data', metadata, autoload=True)
					Data = automap.classes['Data']				# RDS Data table
					
					#Data_res = session.query(Data).filter(Data.created_at == eventtime, Data.ProjectId == project_id, Data.DeviceId == device_id).all()
					Data_res = session.query(Data).filter(Data.data == list2[0]).all()
					
					# get Data Item
					data_item = []
					for data in Data_res:
						data_item = data
						break
					
					try:
						if data_item == empty_lst:
							print("Create new Data")
							# add new Data when the same eventTime is not found
							new_data = Data()

							# 20230329 new RDS version
							new_data.data = list2[0]			# filename
							# update according to file extension
							bucket_name = ''			# (V2)
							if list2[1] == 'jpg':
								new_data.image = 1
								bucket_name = 'image'	# (V2)
							elif list2[1] == 'mp4':
								new_data.video = 1
								bucket_name = 'video'	# (V2)
							elif list2[1] == 'csv':
								new_data.csv = 1
								bucket_name = 'csv'

							new_data.created_at = eventtime
							new_data.updated_at = eventtime
							new_data.ProjectId = project_id
							new_data.DeviceId = device_id
							# user_id would be appended automatically by back-end
							#new_data.UserId = User_id

							session.add(new_data)
							
						else:
							print("Data exists, modify column")
							bucket_name = ''			# (V2)
							if list2[1] == 'jpg':
								data_item.image = 1
								bucket_name = 'image'	# (V2)
							elif list2[1] == 'mp4':
								data_item.video = 1
								bucket_name = 'video'	# (V2)
							elif list2[1] == 'csv':
								data_item.csv = 1
								bucket_name = 'csv'

						# write on RDS
						session.commit()

						# update progress
						uploaded_file_counter += 1
						progress = (float) (uploaded_file_counter / len(self.allFileLise) * 100.0)

					except Exception as e:
						# error
						session.rollback()
						loguru.logger.error('Data created failed!')
						loguru.logger.error(e)

						msg_network_failed = True
						break
						
					try:
						# upload data
						print(f"bucket_name = {bucket_name}, key = {key}")
						s3.Object(bucket_name, key).upload_file(file_path, ExtraArgs = {'ContentType':'*/*'},
							Config = config, Callback = ProgressPercentage(file_path))

						# move to finish upload folder
						#os.replace(file_path, self.UploadSuccess + file)
						
						# delete the file which has been uploaded
						os.remove(file_path)
						
					except Exception as e:
						# error
						session.rollback()
						loguru.logger.error('Files upload to S3 bucket failed')
						loguru.logger.error(e)

						msg_network_failed = True
						break
				
				# close RDS connect
				session.close()

				# upload completed
				progress = 100.0

		except Exception as e:
			if session is not None:
				session.rollback()
				session.close()
			loguru.logger.error('Connect to RDS failed, try to reconnect')
			loguru.logger.error(e)

			msg_network_failed = True

						
class ProgressPercentage(object):
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

def Thread_ZeroMQ():
	# initialize ZeroMQ Server
	context = zmq.Context()
	socket = context.socket(zmq.REP)
	socket.bind("tcp://*:2003")
	
	while True:
		recv_msg = socket.recv().decode('utf-8')
		
		# initialize messages
		global msg_terminate_program
		global msg_upload_videos
		global msg_upload_pictures

		global msg_network_failed
		global msg_hardware_unauth
		global progress
		
		response_str = 'Invalid Command!'
		
		if msg_terminate_program == True:
			break
		
		elif recv_msg == 'TERMINATE':
			socket.send('Exit Upload Manager'.encode())
			msg_terminate_program = True
			break
			
		elif recv_msg == 'upload_videos':
			msg_network_failed = False
			msg_hardware_unauth = False
			progress = 0.0
			msg_upload_videos = True
			
			print("Uploading Videos")
			response_str = 'OK'
			
		elif recv_msg == 'upload_pictures':
			msg_network_failed = False
			msg_hardware_unauth = False
			progress = 0.0
			msg_upload_pictures = True

			print("Uploading Pictures")
			response_str = 'OK'
				
		elif recv_msg == 'progress?':
			if msg_network_failed == True:
				response_str = 'Network Failed!'
			elif msg_hardware_unauth == True:
				response_str = 'Device is not Authorized!'
			elif progress == 0.0:
				response_str = 'Requesting Permission...'
			elif progress == 100.0:
				response_str = 'Done!'
			else:
				response_str = 'Uploading...; ' + ("%.2f" % progress) + '%'
		
		socket.send(response_str.encode())


# create a thread for ZeroMQ message response
thread_zeroMQ = Thread(target=Thread_ZeroMQ, args=())
thread_zeroMQ.start()

if __name__ == '__main__':
	s = requests.session()

	while True:
		if msg_terminate_program:
			break

		elif msg_upload_videos:
			send = SendFile(s, 'rec_pic/', 'videos/', 'vi_uploaded/')
			send.multipart_upload_boto3()
			msg_upload_videos = False
		
		elif msg_upload_pictures:
			send = SendFile(s, 'rec_pic/', 'img_res/', 'img_uploaded/')
			send.multipart_upload_boto3()
			msg_upload_pictures = False
		
		time.sleep(0.5)


# if __name__ == '__main__':
# 	s = requests.session()

# 	if len(sys.argv) != 2:
# 		print("Argument format: [picture/video]")
# 		exit(0)

# 	if sys.argv[1] == "picture":
# 		# Picture upload
# 		send = SendFile(s, 'rec_pic/', 'img_res/', 'img_uploaded/')		# Data path；Picture folder name；Finish data folder name
# 		send.multipart_upload_boto3()
# 	elif sys.argv[1] == "video":
# 		# Video upload
# 		send = SendFile(s, 'rec_pic/', 'videos/', 'vi_uploaded/')		# Data path；video folder name；Finish data folder name
# 		send.multipart_upload_boto3()
# 	elif sys.argv[1] == "both":
# 		# Picture upload
# 		send = SendFile(s, 'rec_pic/', 'img_res/', 'img_uploaded/')		# Data path；Picture folder name；Finish data folder name
# 		send.multipart_upload_boto3()
# 		# Video upload
# 		send = SendFile(s, 'rec_pic/', 'videos/', 'vi_uploaded/')		# Data path；video folder name；Finish data folder name
# 		send.multipart_upload_boto3()

# 	print()
# 	print ('upload finish')

	# loguru.logger.add(
	# 	f'{datetime.date.today():%Y%m%d}.log',
	# 	rotation='1 day',
	# 	retention='7 days',
	# 	level='DEBUG'
	# )
