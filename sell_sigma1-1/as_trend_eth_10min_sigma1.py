from pyparsing import Word
import requests
import json
import time
import pandas as pd
import numpy as np

# パラメータ変更箇所はコメントに"パラメータ変更箇所"と記載している

# 通過はpathのsymbolに記載(詳細はhttps://api.coin.z.com/docs/#ticker)
endPointPublic = 'https://api.coin.z.com/public'
pathGetRate     = '/v1/ticker?symbol=ETH_JPY'
pathGetKline     = '/v1/orderbooks?symbol=ETH_JPY'
pathParams = '../params.txt'

# パラメータを別ファイルから取得
with open(pathParams) as f:
	s = f.readlines()

line_idx_s = s[0].find("=")
line_idx_e = s[0].find("\n")
line_token = s[0][line_idx_s+1:line_idx_e]
api_idx_s = s[1].find("=")
api_idx_e = s[1].find("\n")
apiKey = s[1][api_idx_s+1:api_idx_e]
secret_idx_s = s[2].find("=")
secret_idx_e = s[2].find("\n")
secretKey = s[2][secret_idx_s+1:secret_idx_e]

# ********** function ****************
# LINEに通知する関数
def line_notify(text):
	url = "https://notify-api.line.me/api/notify"
	data = {"message" : text}
	headers = {"Authorization": "Bearer " + line_token}
	requests.post(url, data=data, headers=headers)

# 現在のレートをAPIで取得
def GetRate():
	while True:
		try:
			response = requests.get(endPointPublic + pathGetRate)
			if 'json' in response.headers.get('content-type'):
				data = [response.json()['data'][0]['timestamp'].replace('T',' ')[:-5],response.json()['data'][0]['last']]
				return data
			else:
				data = 0
				return data
		except requests.exceptions.RequestException as e:
			print("最新の価格取得でエラー発生 : ",e)
			print("10秒待機してやり直します")
			time.sleep(10)

# 現在の板取引情報をAPIで取得（売り、買いはそれぞれ最良気配のものを取得）
def GetKline():
	while True:
		try:
			response = requests.get(endPointPublic + pathGetKline)
			if 'json' in response.headers.get('content-type'):
				data = response.json()
				return int(data['data']['asks'][0]['price']), int(data['data']['bids'][0]['price'])
			else:
				data = 0
				return data
		except requests.exceptions.RequestException as e:
			print("最新の板取得でエラー発生 : ",e)
			print("10秒待機してやり直します")
			time.sleep(10)

# 現在地から1分ごとのデータを抽出
# データ間隔を変更する場合はコードを直接編集する必要がある
# パラメータ変更箇所
def ExtractJustTime_1min(time_stamp):
	flag_just_time_1min = False
	time_stamp_int = int(time_stamp[-2:])
	if time_stamp_int >= 58 or time_stamp_int <= 2:
		flag_just_time_1min = True
	return flag_just_time_1min

def ExtractJustTime_10min(time_stamp):
	flag_just_time_10min = False
	time_stamp_int = int(time_stamp[-4:-3])
	if time_stamp_int == 0:
		flag_just_time_10min = True
	return flag_just_time_10min

# BBを計算
def CalcBB(data): # data = [close, ..., close]
	bband = {}
	bband['mean'] = sum(data) / len(data)
	bband['upper'] = bband['mean'] + np.std(data) * 1
	bband['lower'] = bband['mean'] + np.std(data) * (-1)
	return bband

# エントリー、決済、損切りの計算
# デモ用 money
def CalcMain(flag_just_time_1min,flag_just_time_10min,element,money,money_tmp):

	# APIでポジションしているか確認する処理を追加

	kline = [] # デモ用

	if flag_just_time_10min:
		if flag_just_time_1min: # 58~2秒のデータをdata_sumに格納
			element['data_sum'].append(int(data_now[1]))
		elif len(element['data_sum']) > 0: # 58~2秒以外かつelement['data_sum']の要素が要素が0以上の時BBに使うデータを計算する
			element['data_ave'] = sum(element['data_sum']) / len(element['data_sum'])
			element['data_sum'] = []
			element['data_bb_20'].append(round(element['data_ave']))
			element['cnt_bb_20'] += 1
			if element['cnt_bb_20'] == 20: # BBで使うデータが20個揃ったらBBを計算する
				element['data_bb'] = CalcBB(element['data_bb_20']) ## element['data_bb_20']からBBを計算する
				# デモ用
				print("money=" + str(money) + ",close=" + str(data_now[1]),end=",")
				print(element['data_bb'],end=",")
				with open('10min_eth_BB_sigma1.csv', mode='a') as f:
					print("money=" + str(money) + ",close=" + str(data_now[1]),end=",", file=f)
					print(element['data_bb'],end=",", file=f)
				# エントリーまたは決済の処理
				if element['flag_position'] == "BUY" or element['flag_position'] == "SELL": # ポジションが入っている時の処理
					if (int(data_now[1]) <= int(element['data_bb']['mean']) and element['flag_position'] == "BUY" ) or (int(data_now[1]) >= int(element['data_bb']['mean']) and element['flag_position'] == "SELL"):
						# 損切りの処理
						# デモ用
						print("損切り", end=',')
						with open('10min_eth_BB_sigma1.csv', mode='a') as f:
							print("損切り",end=",", file=f)
						while True:
							kline = GetKline()
							if kline == 0: # APIでJSONが返ってこなかった時の処理
								print('not json')
								time.sleep(1)
								continue
							else:
								break
						if element['flag_position'] == "BUY":
							money += (kline[1] - money_tmp)
							line_notify("損切り(ロング):" + str(kline[1]))
						else:
							money += (money_tmp - kline[0])
							line_notify("損切り(ショート):" + str(kline[0]))
						element['flag_position'] = "NO"
					elif int(data_now[1]) <= int(element['data_bb']['upper']) and element['flag_position'] == "BUY":
						element['flag_plus'] -= 1
					elif int(data_now[1]) >= int(element['data_bb']['lower']) and element['flag_position'] == "SELL":
						element['flag_minus'] -= 1
					else:
						element['flag_plus'] = 0
						element['flag_minus'] = 0
					if element['flag_plus'] == -1 or element['flag_minus'] == -1: # -σ1を1回超えたら決済
						# 決済処理
						# デモ用
						while True:
							kline = GetKline()
							if kline == 0:
								print('not json')
								time.sleep(1)
								continue
							else:
								break
						if element['flag_position'] == "BUY":
							money += (kline[1] - money_tmp)
							line_notify("決済(ロング):" + str(kline[1]))
						else:
							money += (money_tmp - kline[0])
							line_notify("決済(ショート):" + str(kline[0]))
						element['flag_position'] = "NO"
						element['flag_plus'] = 0
						element['flag_minus'] = 0
						print("決済処理", end=",")
						with open('10min_eth_BB_sigma1.csv', mode='a') as f:
							print("決済処理",end=",", file=f)
				else: # ポジションが入っていない時の処理
					if int(data_now[1]) >= int(element['data_bb']['upper']):
						element['flag_plus'] += 1
						element['flag_minus'] = 0
					elif int(data_now[1]) <= int(element['data_bb']['lower']):
						element['flag_minus'] += 1
						element['flag_plus'] = 0
					else:
						element['flag_plus'] = 0
						element['flag_minus'] = 0
					if element['flag_plus'] == 3 or element['flag_minus'] == 3:
						# 注文処理
						if element['flag_plus'] == 3:
							element['flag_position'] = "BUY"
						else:
							element['flag_position'] = "SELL"
						element['flag_plus'] = 0
						element['flag_minus'] = 0

						# デモ用
						while True:
							kline = GetKline()
							if kline == 0:
								print('not json')
								time.sleep(1)
								continue
							else:
								break
						if element['flag_position'] == "BUY":
							money_tmp = kline[0]
							line_notify("注文処理(ロング):" + str(kline[0]))
						else:
							money_tmp = kline[1]
							line_notify("注文処理(ショート):" + str(kline[1]))
						print("注文処理", end=",")
						with open('10min_eth_BB_sigma1.csv', mode='a') as f:
							print("注文処理",end=",", file=f)

				element['data_bb_20'] = element['data_bb_20'][1:] # element['data_bb_20']の先頭データを削除する
				element['cnt_bb_20'] = 19 # 直前の20個のデータから19個を使うので初回以降はelement['cnt_bb_20']=19とすることで1個だけ新しいデータを追加する
			# デモ用
			print(data_now[0] +  ",element['flag_position']=" + element['flag_position'] + ",element['flag_plus']=" + str(element['flag_plus']) + ",element['flag_minus']=" + str(element['flag_minus']))
			with open('10min_eth_BB_sigma1.csv', mode='a') as f:
				print(data_now[0] +  ",element['flag_position']=" + element['flag_position'] + ",element['flag_plus']=" + str(element['flag_plus']) + ",element['flag_minus']=" + str(element['flag_minus']), file=f)

	# デモ用　money,money_tmp
	return element,money,money_tmp
# ********** function ****************


# ******* main *************
# 変数
# data_sum = [] # BBで使うデータをリアルタイムデータの平均から算出するためのデータ
# data_ave = 0 # BBで使う1個のデータ
# data_bb_20 = [] # BBで使う20個のデータ
# data_bb = {} ## BB
# cnt_bb_20 = 0 # BBで使う20個のデータを取得する際に使うカウンタ
# cnt_bb = 0 # BBをdata_bbに保存する際に使うカウンタ
# flag_plus = 0 # +1σを3回連続で超えたらエントリー、+1σを2回連続で超えたら決済 -> この条件を判断するためのカウンタ
# flag_minus = 0 # -1σを3回連続で超えたらエントリー、-1σを2回連続で超えたら決済 -> この条件を判断するためのカウンタ
# flag_position = "NO" # "":ポジションなし、"BUY":買い、"SELL":売り

element = {
	'data_sum': [],
	'data_ave': 0,
	'data_bb_20': [],
	'data_bb': {},
	'cnt_bb_20': 0,
	'cnt_bb': 0,
	'flag_plus': 0,
	'flag_minus': 0,
	'flag_position': "NO"
}

money = 0 # デモ用の所持金の変数
money_tmp = 0 # デモ用の売買の差引に使う変数

# 1秒毎にAPIを叩いてレートを取得する
while True:
	data_now = GetRate()
	if data_now == 0: # APIでJSONが返ってこなかった時の処理
		continue
	flag_just_time_1min = ExtractJustTime_1min(data_now[0])
	flag_just_time_10min = ExtractJustTime_10min(data_now[0])
	# デモ用
	# ポジションの有無をAPIで取得するからflaf_positionは消す
	element,money,money_tmp = CalcMain(flag_just_time_1min,flag_just_time_10min,data_now,element,money,money_tmp)

	time.sleep(1)
# ******* main *************
