import json
import requests
from time import sleep
import datetime
import os

data_filepath = "./data"
json_filepath = "./set.json"
api_get_orders = 'https://api.warframe.market/v1/items/{}/orders'
# Note that the Warframe.market devs have requested 3rps limit
# Therefore, I cache results, only running a GET if the results are more than ** 1hr ** old

last_cache_time = {}

# Read the last cache times from the saved data files
def update_last_cache_time():
	if not os.path.isdir(data_filepath):
		os.mkdir(data_filepath)
	for filename in os.listdir(data_filepath):
		with open(data_filepath+'/'+filename) as data_file:
			last_cache_time[filename] = datetime.datetime.fromtimestamp(float(data_file.readline()))


# Query the list of relics to see if the input is valid
def search(query, relic_list):
	query_target = None

	for relic in relic_list:
		# dumb search assumes only one to be found
		if relic['name'] == query:
			query_target = relic

	return query_target


# Convert human readable name to url
def name_to_url(name):
	return name.lower().replace(' ', '_')


# Either pull data from cache or make GET request depending on the circumstance
def cache_or_api(name, refresh):
	url = name_to_url(name)
	time_now = datetime.datetime.now()
	hour = datetime.timedelta(hours=1)

	# If the data is in the cache and is recent and no force refresh
	if not refresh:
		if url in last_cache_time:
			if time_now - last_cache_time[url] < hour:
				print("Loading {} data from cache...".format(name))
				with open(data_filepath+'/'+url, 'r') as file:
					file.readline()
					return json.loads(file.read())

	# Otherwise, need to use GET request to update cache
	print("Fetching {} data from Warframe.Market...".format(name))
	last_cache_time['url'] = time_now
	res = requests.get(api_get_orders.format(url))
	sleep(0.5)
	# TODO: some kind of bucket system to make this more efficient? don't need to wait in some cases
	with open(data_filepath+'/'+url, 'w') as file:
		file.write(str(time_now.timestamp())+'\n')
		file.write(res.text)
	return res.json()


# Only want some results
def filter_orders(orders):
	online_orders = [x for x in orders if x['user']['status'] == 'ingame']
	visible_orders = [x for x in online_orders if x['visible'] == True]
	pc_orders = [x for x in visible_orders if x['platform'] == 'pc']
	en_orders = [x for x in pc_orders if x['region'] == 'en']
	sell_orders = [x for x in en_orders if x['order_type'] == 'sell']
	sorted_orders = sorted(sell_orders, key=lambda x: x["platinum"])
	truncated = sorted_orders[:5]
	return truncated


# Calculates a weighted average of the prices of each possible drop
# Each possible drop's price is the average of the 5 lowest 'online in game' users
def calculate(relic, probabilities, refresh):
	weighted_average = 0

	for drop in relic['drops']:
		price = 0
		res = cache_or_api(drop['name'], refresh)

		# Need to check if we actually have a payload or an error
		if 'payload' in res:
			filtered = filter_orders(res['payload']['orders'])
# Naively assumes that average of the cheapest 5 sell offers is the value of the item
			for offer in filtered:
				price += offer['platinum']
			price /= len(filtered)

		probability = probabilities[drop['rarity']]
		weighted_average += price * probability

	return weighted_average

# Read data json
json_data = json.loads(open(json_filepath).read())
probabilities = json_data['probabilities']
relics = json_data['relics']

# Load the last_cache_time into memory
update_last_cache_time()

print("Warframe Void Relic price checker. All prices pulled from Warframe.Market.")
print("Can use -q <intact|exceptional|flawless|radiant> to specify quality.")
print("If no quality is specified, intact is the default.")
print("Can use -r to force update the prices. This slows down the query by a lot.")

# Ask for searches until 'exit'
while(True):
	query = input("\nWhich relic? ")
	if query == 'exit':
		break;

	# Clean up input, and partition into relic_name and query_flags
	cleanup = query.split(' ')[:2]
	cleanup[0] = cleanup[0].lower().capitalize()
	cleanup[1] = cleanup[1].upper()
	relic_name = ' '.join(cleanup)
	query_flags = query.split(' ')[2:]

	# can use -r flag to force cache refresh
	refresh = False
	if '-r' in query_flags:
		refresh = True

	# can use -q <intact|exceptional|flawless|radiant> to account for quality
	quality = "intact"
	if '-q' in query_flags:
		if len(query_flags) < query_flags.index('-q')+1:
			print("Error: '-q' must be followed by a quality")
		else:
			after_q = query_flags[query_flags.index('-q')+1].lower()
			if quality == 'intact' or quality == 'exceptional' or quality == 'flawless' or quality == 'radiant':
				quality = after_q
			else:
				print("Error: quality must be one of 'intact', 'exceptional', 'flawless', or 'radiant'")


	ret = search(relic_name, relics)

	if ret == None:
		print("Invalid query: No matches found")
	else:
		value = calculate(ret, probabilities[quality], refresh)
		print("\nExpected value of {} {}: {}".format(quality.capitalize(), relic_name, value))

