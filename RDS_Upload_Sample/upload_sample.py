import requests
import threading
import os
import boto3
import sys
import cv2
import shutil
import time
import datetime
import loguru
import sqlalchemy
import sqlalchemy.ext.automap
import sqlalchemy.orm
import sqlalchemy.schema
from boto3.s3.transfer import TransferConfig


save_path = './to-be-uploaded'
file_destination = './uploaded'


# initialize variables
cpu_serial = "LAPTOP-KJAT43UT"
DeviceID = "0x72"
#folder = 'Pictures/Dinasour/'
folder = 'Pictures/Helmet/'
#project_name = "ProjectD"	# append project name when calling filename_append_project_name()

username = 'admin'     # RDS account
password = 'instai76666'     # RDS password
#host = 'carview.cvprqxu67qc8.us-east-1.rds.amazonaws.com'    # RDS address version1
# 0921 RDS version2
#host = 'db-carview-v2.cvprqxu67qc8.us-east-1.rds.amazonaws.com'    # RDS address version2
#host = 'db-instai.cvprqxu67qc8.us-east-1.rds.amazonaws.com'
host = 'instai-rds.cwxva4x4deuv.us-east-1.rds.amazonaws.com'
port = '3306'         # RDS port
#database = 'carview'   # RDS name
database = 'myDB'     # version2
engine = sqlalchemy.create_engine(f'mysql+pymysql://{username}:{password}@{host}:{port}/{database}',echo=False)


config = TransferConfig(multipart_threshold = 1024*10,		# more than 10MB
			max_concurrency = 10,			
			multipart_chunksize = 1024*10,		# multipart size
			use_threads = True)			# S3 multi thread transmit


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
		empty_lst = []	# define empty table
		
		# get RDS data
		metadata = sqlalchemy.schema.MetaData(engine)
		# auto map RDS data
		automap = sqlalchemy.ext.automap.automap_base()
		automap.prepare(engine, reflect=True)

		# ORM connect 
		session = sqlalchemy.orm.Session(engine)

		#sqlalchemy.Table('CarNumber', metadata, autoload=True)
		# (V2)
		sqlalchemy.Table('Devices', metadata, autoload=True)
		
		# 0921 table name modification
		Devices = automap.classes['Devices']			# RDS Projects table

		loguru.logger.info('Filtering Table Devices')
		Device_res = []
		#res1 = session.query(CarNumber1).filter(CarNumber1.boardId == boardid).all()	# get this boardId's Table
		Device_res = session.query(Devices).filter(Devices.serialNumber == cpu_serial).all()	# (V2) get this boardId's Table
		# get Device Id and Project Id
		Device_id = []
		Project_id = []
		for device in Device_res:
			Device_id = device.id
			Project_id = device.ProjectId
			accesskey = device.accessKey			# get accessKey
			secretkey = device.secretKey			# get secretKey
		if (Device_id == empty_lst) or (Project_id == empty_lst) :
			# boardId isn't in RDS
			session.rollback()
			loguru.logger.error('Hardware is not authorized')
			# close RDS connect
			session.close()
		else:
			loguru.logger.info('Accessing S3')
			s3 = boto3.resource('s3', aws_access_key_id=os.getenv('AWS_S3_ACCESS_KEY_ID', accesskey),	# S3 login setting 
							aws_secret_access_key=os.getenv('AWS_S3_SECRET_ACCESS_KEY', secretkey), endpoint_url='https://lab321-carview.s3-accelerate.amazonaws.com')
			
			# append project name in folder
			#self.filename_append_project_name()
			# refresh filename in directory
			self.allFileLise = sorted(os.listdir(self.dir))

			for file in self.allFileLise:
				list1 = file.split('_')				# filename split
				list2 = file.split('.')				# main filename split
				file_path = self.dir + file			# data path include filename
				key = file					# aws target path
				bucket_upload_folder = self.upload.split('/')[0] 
				eventtime = list1[2][0:4] + '-' + list1[2][4:6] + '-' + list1[2][6:8] + ' ' + list1[2][8:10] + ':' + list1[2][10:12] + ':' + list1[2][12:14]		# file event time
				#eventtime = list1[3][0:4] + '-' + list1[3][4:6] + '-' + list1[3][6:8] + ' ' + list1[3][8:10] + ':' + list1[3][10:12] + ':' + list1[3][12:14]		# file event time (V2)
				
				# ORM connect (no need to reconnect to RDS everytime)
				#session = sqlalchemy.orm.Session(engine)
				# get Event list
				#sqlalchemy.Table('Event', metadata, autoload=True)
				# (V2)
				loguru.logger.info('Filtering Table Data')
				sqlalchemy.Table('Data', metadata, autoload=True)
				#Event1 = automap.classes['Event']				# RDS Data table
				Data = automap.classes['Data']				# RDS Data table (V2)
				
				#res2 = session.query(Event1).filter(Event1.eventTime == eventtime, Event1.carNumberId == resn1).all()
				# (V2)
				Data_res = session.query(Data).filter(Data.data == list2[0],Data.created_at == eventtime, Data.ProjectId == Project_id, Data.DeviceId == Device_id).all()
				
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
						new_data.ProjectId = Project_id
						new_data.DeviceId = Device_id
						#new_data.UserId = User_id

						session.add(new_data)
						
					else:
						print("Data Exists")
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

				except Exception as e:
					# error
					session.rollback()
					loguru.logger.error('Data created failed!')
					loguru.logger.error(e)
					break
					
				try:
					# upload data
					print(f"bucket_name = {bucket_name}, key = {key}")
					s3.Object(bucket_name, key).upload_file(file_path, ExtraArgs = {'ContentType':'*/*'},
						Config = config, Callback = ProgressPercentage(file_path))

					# move to finish upload folder
					#os.replace(file_path, self.UploadSuccess + file)
					
				except Exception as e:
					# error
					session.rollback()
					loguru.logger.error('Files upload to S3 bucket failed')
					loguru.logger.error(e)
					break

			# close RDS connect
			session.close()

						
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


if __name__ == '__main__':


	s = requests.session()


	get_files = os.listdir(save_path)
	print(get_files)
	file_pictures = input('select your target:')
	file_source = save_path+'/'+file_pictures+'/'
	# Picture upload
	send = SendFile(s, '', file_source, '')		# Data path；Picture folder name；Finish data folder name
	send.multipart_upload_boto3()

	print()
	print ('upload finish')

	loguru.logger.add(
		f'{datetime.date.today():%Y%m%d}.log',
		rotation='1 day',
		retention='7 days',
		level='DEBUG'
	)
	shutil.move(file_source , file_destination)


	
