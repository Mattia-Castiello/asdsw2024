import socket
from sys import argv
import logging
import re
import json

def decodeJoin(addr, mess):
    result = re.search('(\{[a-zA-Z0-9\"\'\:\.\, ]*\})' , mess)
    if bool(result):
        logging.debug('RE GROUP(1) {}'.format(result.group(1)))
        action = json.loads(result.group(1))
    else:
        action = {}
    
    action['command'] = 'join'

    return action

def decodeLeave(addr, mess):
    result = re.search('(\{[a-zA-Z0-9\"\'\:\.\, ]*\})' , mess)
    if bool(result):
        logging.debug('RE GROUP(1) {}'.format(result.group(1)))
        action = json.loads(result.group(1))
    else:
        action = {}
    
    action['command'] = 'leave'
    
    return action

def decodeMessage(addr, mess):
    result = re.search('^\[([A-Z]*)\]' , mess)
    if bool(result):
        command = result.group(1)
        logging.debug('COMMAND: {}'.format(command))

        try:
            action = {
                'JOIN'  : lambda param1,param2 : decodeJoin(param1, param2),
                'LEAVE' : lambda param1,param2 : decodeLeave(param1, param2)
            }[command](addr, mess)
        except:
            action = {}
            action['command'] = 'unknown'
    else:
        action = {}
        action['command'] = 'invalid'

    logging.debug('ACTION: {}'.format(action))

    return action

def updateRingJoin(action, listOfNodes):
    logging.debug('RING JOIN UPDATE')
    node = {}

    id_ = 1
    idList = [int(eNode['id']) for eNode in listOfNodes]
    for i in range(1, len(listOfNodes)+2):
        if i not in idList:
            id_ = i
            break
    
    node['id']   = str(id_)
    node['port'] = action['port']
    node['addr'] = action['addr']

    # Verifica esistenza nodo nella lista di nodi
    nodes = [(eNode['addr'], eNode['port']) for eNode in listOfNodes]

    if (node['addr'], node['port']) not in nodes:
        logging.debug('OK:  Adding node {}:{}'.format(node['addr'], node['port']))
        listOfNodes.append(node)
    else:
        logging.debug('NOK: Adding node {}:{}'.format(node['addr'], node['port']))
        return False
    #
    return True

def updateRingLeave(action, listOfNodes):
    logging.debug('RING LEAVE UPDATE')

    #
    dictOfNodes = {eNode['id'] : eNode for eNode in listOfNodes}
    
    if action['id'] not in dictOfNodes:
        logging.debug('NOK: Remove node {}:{}'.format(action['addr'],action['port']))
        return False

    nodeToRemove = dictOfNodes[action['id']]
    #scorro la lista of nodes fatte di duple, per cui ogni id è il nodo stesso
    logging.debug('Removing node {}:{}'.format(nodeToRemove['addr'], nodeToRemove['port']))
    #verifico se l'id di cui sto facendo il...faccia parte del dizionario
    if action['addr'] == nodeToRemove['addr'] and action['port'] == nodeToRemove['port']:
        #prendo il nodo() se esiste e verifico che l'ip eil porto siano quelligiusti, potrebbe
        #capitare che l'ip sia sbaglaito  e tolgo un altro nodo, ma con il controllo sul porto ciò non può capitare
        logging.debug('OK:  Remove node {}:{}'.format(action['addr'],action['port']))

        listOfNodes.remove(nodeToRemove)
    else:
        #esco se non esiste 
        logging.debug('NOK: Remove node {}:{}'.format(action['addr'],action['port']))
        return False
    #
    return True

def updateRing(action, listOfNodes, oracleSocket):
    logging.info('RING UPDATE: {}'.format(action))
    
    try:
        result = {
            'join'  : lambda param1,param2 : updateRingJoin(param1, param2),
            'leave' : lambda param1,param2 : updateRingLeave(param1, param2)
        }[action['command']](action, listOfNodes)
    except:
        result = False
        return result

    sendConfigurationToAll(listOfNodes, oracleSocket)
    
    return result
#viene fatto semplicemente un invio dei messaggi a tutti
def sendConfigurationToAll(listOfNodes, oracleSocket):
    N = len(listOfNodes)
    #ciclo for sulla listofnodes aggiornata
    #identifico il nodo successivo per ogni nodo
    #gli dico il nodo 
    for idx, node in enumerate(listOfNodes):
        if idx == N-1:
            nextNode = listOfNodes[0]
        else:
            nextNode = listOfNodes[idx + 1]
        #logging.debug('UPDATE NODE: ({}) {}:{} --> ({}) {}:{}'.format(\
        #        node['id'],     node['addr'],     node['port'], \
        #        nextNode['id'], nextNode['addr'], nextNode['port']))
        #prendo i riferimenti del nodo da contattare
        addr, port = node['addr'], int(node['port'])
        message = {}
        message['id'] = node['id']
        #messaggio è un json che contiene l'id a cui appartiene lui, e le info sul nextcode 
        message['nextNode'] = nextNode
        message = '[CONF] {}'.format(json.dumps(message))
        logging.debug('UPDATE MESSAGE: {}'.format(message))
        oracleSocket.sendto(message.encode(), (addr, port))
        #

if __name__ == '__main__':

    IP     = argv[1]
    PORT   = int(argv[2])
    bufferSize  = 1024
    listOfNodes = []

    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)

    oracleSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    oracleSocket.bind( (IP, PORT) )

    logging.info("ORACLE UP AND RUNNING!")

    while True:
        mess, addr = oracleSocket.recvfrom(bufferSize)
        dmess = mess.decode('utf-8')

        logging.info('REQUEST FROM {}'.format(addr))
        logging.info('REQUEST: {}'.format(dmess))

        action = decodeMessage(addr, dmess)
        updateRing(action, listOfNodes, oracleSocket)

        logging.info('UPDATED LIST OF NODES {}'.format(listOfNodes))
