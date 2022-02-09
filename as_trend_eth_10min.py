from pyparsing import Word
import requests
import json
import time
import pandas as pd
import numpy as np

# パラメータ変更箇所はコメントに"パラメータ変更箇所"と記載している

# GMOコインのAPI
# 通過はpathのsymbolに記載(詳細はhttps://api.coin.z.com/docs/#ticker)
# パラメータ変更箇所
endPoint = 'https://api.coin.z.com/public'
pathGetRate     = '/v1/ticker?symbol=ETH_JPY'
pathGetKline     = '/v1/orderbooks?symbol=ETH_JPY'

# ********** function ****************
# 現在のレートをAPIで取得
def GetRate():
	while True:
		try:
			response = requests.get(endPoint + pathGetRate)
			data = [response.json()['data'][0]['timestamp'].replace('T',' ')[:-5],response.json()['data'][0]['last']]
			return data
		except requests.exceptions.RequestException as e:
			print("最新の価格取得でエラー発生 : ",e)
			print("10秒待機してやり直します")
			time.sleep(10)

# 現在の板取引情報をAPIで取得（売り、買いはそれぞれ最良気配のものを取得）
def GetKline():
	while True:
		try:
			response = requests.get(endPoint + pathGetKline)
			data = response.json()
			return int(data['data']['asks'][0]['price']), int(data['data']['bids'][0]['price'])
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
def CalcMain(flag_just_time_1min, flag_just_time_10min, data_now,data_sum, data_bb_20, cnt_bb_20, flag_plus, flag_minus, flag_position, money,money_tmp):

	# APIでポジションしているか確認する処理を追加

	kline = [] # デモ用

	if flag_just_time_10min:
		if flag_just_time_1min: # 58~2秒のデータをdata_sumに格納
			data_sum.append(int(data_now[1]))
		elif len(data_sum) > 0: # 58~2秒以外かつdata_sumの要素が要素が0以上の時BBに使うデータを計算する
			data_ave = sum(data_sum) / len(data_sum)
			data_sum = []
			data_bb_20.append(round(data_ave))
			cnt_bb_20 += 1
			if cnt_bb_20 == 20: # BBで使うデータが20個揃ったらBBを計算する
				data_bb = CalcBB(data_bb_20) ## data_bb_20からBBを計算する
				# デモ用
				print("money=" + str(money) + ",close=" + str(data_now[1]),end=",")
				print(data_bb,end=",")
				with open('1min_eth_BB.csv', mode='a') as f:
					print("money=" + str(money) + ",close=" + str(data_now[1]),end=",", file=f)
					print(data_bb,end=",", file=f)
				# エントリーまたは決済の処理
				if flag_position == "BUY" or flag_position == "SELL": # ポジションが入っている時の処理
					if (int(data_now[1]) <= int(data_bb['mean']) and flag_position == "BUY" ) or (int(data_now[1]) >= int(data_bb['mean']) and flag_position == "SELL"):
						# 損切りの処理
						# デモ用
						print("損切り", end=',')
						with open('1min_eth_BB.csv', mode='a') as f:
							print("損切り",end=",", file=f)
						kline = GetKline()
						if flag_position == "BUY":
							money += (kline[0] - money_tmp)
						else:
							money += (money_tmp - kline[1])
						flag_position = "NO"
					elif int(data_now[1]) <= int(data_bb['upper']) and flag_position == "BUY":
						flag_plus -= 1
					elif int(data_now[1]) >= int(data_bb['lower']) and flag_position == "SELL":
						flag_minus -= 1
					else:
						flag_plus = 0
						flag_minus = 0
					if flag_plus == -2 or flag_minus == -2:
						# 決済処理
						# デモ用
						kline = GetKline()
						if flag_position == "BUY":
							money += (kline[0] - money_tmp)
						else:
							money += (money_tmp - kline[1])
						flag_position = "NO"
						flag_plus = 0
						flag_minus = 0
						print("決済処理", end=",")
						with open('1min_eth_BB.csv', mode='a') as f:
							print("決済処理",end=",", file=f)
				else: # ポジションが入っていない時の処理
					if int(data_now[1]) >= int(data_bb['upper']):
						flag_plus += 1
						flag_minus = 0
					elif int(data_now[1]) <= int(data_bb['lower']):
						flag_minus += 1
						flag_plus = 0
					else:
						flag_plus = 0
						flag_minus = 0
					if flag_plus == 3 or flag_minus == 3:
						# 注文処理
						if flag_plus == 3:
							flag_position = "BUY"
						else:
							flag_position = "SELL"
						flag_plus = 0
						flag_minus = 0

						# デモ用
						kline = GetKline()
						if flag_position == "BUY":
							money_tmp = kline[0]
						else:
							money_tmp = kline[1]
						print("注文処理", end=",")
						with open('1min_eth_BB.csv', mode='a') as f:
							print("注文処理",end=",", file=f)

				data_bb_20 = data_bb_20[1:] # data_bb_20の先頭データを削除する
				cnt_bb_20 = 19 # 直前の20個のデータから19個を使うので初回以降はcnt_bb_20=19とすることで1個だけ新しいデータを追加する
			# デモ用
			print(data_now[0] +  ",flag_position=" + flag_position + ",flag_plus=" + str(flag_plus) + ",flag_minus=" + str(flag_minus))
			with open('1min_eth_BB.csv', mode='a') as f:
				print(data_now[0] +  ",flag_position=" + flag_position + ",flag_plus=" + str(flag_plus) + ",flag_minus=" + str(flag_minus), file=f)

	# デモ用　money,money_tmp
	return data_sum,data_bb_20,cnt_bb_20,flag_plus,flag_minus,flag_position,money,money_tmp
# ********** function ****************


# ******* main *************
# 変数
data_sum = [] # BBで使うデータをリアルタイムデータの平均から算出するためのデータ
data_ave = 0 # BBで使う1個のデータ
data_bb_20 = [] # BBで使う20個のデータ
data_bb = {} ## BB
cnt_bb_20 = 0 # BBで使う20個のデータを取得する際に使うカウンタ
cnt_bb = 0 # BBをdata_bbに保存する際に使うカウンタ
flag_plus = 0 # +1σを3回連続で超えたらエントリー、+1σを2回連続で超えたら決済 -> この条件を判断するためのカウンタ
flag_minus = 0 # -1σを3回連続で超えたらエントリー、-1σを2回連続で超えたら決済 -> この条件を判断するためのカウンタ
flag_position = "NO" # "":ポジションなし、"BUY":買い、"SELL":売り

money = 0 # デモ用の所持金の変数
money_tmp = 0 # デモ用の売買の差引に使う変数

# 1秒毎にAPIを叩いてレートを取得する
while True:
	data_now = GetRate()
	flag_just_time_1min = ExtractJustTime_1min(data_now[0])
	flag_just_time_10min = ExtractJustTime_10min(data_now[0])
	# デモ用
	# ポジションの有無をAPIで取得するからflaf_positionは消す
	data_sum,data_bb_20,cnt_bb_20,flag_plus,flag_minus,flag_position,money,money_tmp = CalcMain(flag_just_time_1min,flag_just_time_10min,data_now,data_sum,data_bb_20,cnt_bb_20,flag_plus,flag_minus,flag_position,money,money_tmp)

	time.sleep(1)
# ******* main *************
