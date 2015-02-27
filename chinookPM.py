from bs4 import BeautifulSoup
import urllib2
import pymongo
import sys
import copy
import re

def af_Links(urlSource):
	# Will return a list of links to individual listings if given the url for a company's Appfolio page
	urlBase = urlSource[:(urlSource.index('/',10))]
	chinookList = urllib2.urlopen(urlSource).read()
	soup = BeautifulSoup(chinookList)

	getTheLinks = soup.find_all("a", class_="js-link-to-detail")
	linkS = []

	for link in getTheLinks:
		linkS.append(urlBase + (link.get('href')))

	linkS = set(linkS)
		
	return linkS

chinookSource = 'https://chinookproperties.appfolio.com/listings/'
newList = af_Links(chinookSource)

connection = pymongo.Connection("mongodb://localhost", safe=True)
db = connection.project
listings = db.listings

crawlList = copy.copy(newList) ##going to crawl crawlList after it has been modified

for saidLink in newList: # Remove Listings from new list to crawl that I already have in the DB
	querry = listings.find_one({"_id":saidLink})
	if querry == {"_id":saidLink}:
		crawlList.remove(saidLink)

currentDB = listings.find({"origin":"ChinookPM"},{"_id":1})

for listing in currentDB: # Removes Listings from DB that are not currently listed on Chinook's Website
	if listing["_id"] in newList:
		pass
	else:
		listings.remove(listing)

## At this point crawlList is the var containing a list of urls that need to be crawled and added to the DB

#chinnokCrawl takes one input, a current individual chinook listing and returns a json document of its conents ready to insert into db
def chinookCrawl(listingURL):
	soup = BeautifulSoup(urllib2.urlopen(listingURL).read())
	soupStrings = soup.find_all(text=True)
	urlBase = listingURL[:(listingURL.index('/',10))]

	jsonDoc = {}
	jsonDoc["_id"] = listingURL
	jsonDoc["origin"] = "ChinookPM"
	jsonDoc["title"] = soup.find("h1",class_="align_left").string

#	jsonDoc["type"] = "house"

	#get rental cost as integer, removing comma if present in value
	costLoc = soupStrings.index('Rent:')
	cost= soupStrings[costLoc+1].strip()
	costInt = int(cost[1:].replace(',',''))
	jsonDoc["cost"] = costInt

	#lease term in months as an integer, 1 indicating month to month, 0 for unspecified
#	jsonDoc["leaseTerm"] : 12

	#cost type is static for Chinook PM because they only offer Monthly Rentals
	jsonDoc["costType"] = "Per Month"

	#get listing location
	locOne = soup.find("div", class_="unit_address").contents
	addressString = locOne.pop().strip()
	addressStop = addressString.find(',')
	cityString = addressString[addressStop+1:]
	cityStop = cityString.find(',')
	address = addressString[:addressStop]
	city = cityString[:cityStop]
	zip_code = cityString[-5:]
	state = "Oregon"
	jsonDoc["location"] = {
		"city": city,
		"state": state,
		"zip_code": zip_code,
		"county": "Lane", ## going to implement a reference dictionary for zip codes to counties 
		"address": address,
	}

	jsonDoc["description"] = soup.find("p",class_="align_left").string.strip()

	#get list of images in listing
	imageObject = soup.find_all("a", class_="highslide")
	imageList = []
	for link in imageObject:
		imageList.append(link.get('href'))
	jsonDoc["images"] = imageList

#	jsonDoc["pets"] = {
#		"dogs": true,
#		"cats": false,
#		"petDeposit" : 20,
#		"petRent" : 100,
#	}

	#expand amenities to include Parking, use a nested json doc
#	jsonDoc["amenities"] = [ "string1", "string2", "stringEtc"]

	#get square footage as an integer
	sqfLoc = soupStrings.index('Square feet:')
	sqf = soupStrings[sqfLoc+1]
	jsonDoc["sizeSQF"] = int(sqf.replace(',',''))

	#get int for bedrooms and bathrooms * NOTE THIS WILL NOT WORK IF THERE ARE MORE THAN 9 BEDROOMS OR BATHROOMS
	bedBath = soup.find("div",class_="dark_grey_box").string.strip()
	bedrooms = int(bedBath[0])
	slashLoc = bedBath.index('/')
	bathrooms = int(bedBath[slashLoc+2])
	jsonDoc["bedrooms"] = bedrooms
	jsonDoc["bathrooms"] = bathrooms

	#get available date as a string
	availLoc = soupStrings.index('Available:')
	availDate = soupStrings[availLoc+1].strip()
	jsonDoc["available"] = availDate

	#get application fee as an int
	aFeeLoc = soupStrings.index('Application Fee:')
	aFee = soupStrings[aFeeLoc+1].strip()
	appFee = int(aFee[1:])
	jsonDoc["appFee"] = appFee

	#get security deposit as an integer, must remove comma from value to create integer
	secDepLoc = soupStrings.index('Security Deposit:')
	secDep = soupStrings[secDepLoc+1].strip()
	securityDeposit = int(secDep[1:].replace(',',''))
	jsonDoc["secDeposit"] = securityDeposit

	#Does this listing accept Section 8, HACSA, and is it geared towards students? Uses booleans
	#Will need script to determine if listing is student geared, set student to boolean var***********
	jsonDoc["targetCustomers"] = {
		"Section8" : False,
		"HACSA" : False,
		"Student" : False,
		}

	#Link to Apply if present
	applyObject = soup.find_all(href=re.compile("rental_applications"))[0]
	applyNow = urlBase + applyObject.get('href')
	jsonDoc["ApplyNow"] = applyNow

	#Chinook Property Management Contact info is static
	jsonDoc["Contact"] = {
			"Name" : "Chinook Properties",
			"Address" : "1590 High St. Eugene, OR 97401",
			"Phone" : "(541) 484-0493",
			"Fax" : "(541) 343-7507",
			"Email" : "info@chinookproperties.net",
			"Hours" : "Monday-Friday 9 AM - 5PM"
		}

	return jsonDoc

for listing in crawlList:   #FINAL STEP!
	listings.insert(chinookCrawl(listing))



##  THEN for each LINK in newList querry DB if in DB then remove from newList, if not in DB then do nothing

## What I should be left with is a list of links to listings that need to be crawled to update the DB 

## FOR EACH LINK in NEW LIST we soup it up and get each parameter and place it in a list, I WANT A LIST OF LISTS; POSITION IS IMPORTANT then INSERT VIA LIST POSITION INTO DB
