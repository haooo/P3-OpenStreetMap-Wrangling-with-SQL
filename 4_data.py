import csv
import codecs
import re
import xml.etree.cElementTree as ET

import cerberus

import schema

OSM_PATH = "phoenix_arizona.osm"

NODES_PATH = "nodes.csv"
NODE_TAGS_PATH = "nodes_tags.csv"
WAYS_PATH = "ways.csv"
WAY_NODES_PATH = "ways_nodes.csv"
WAY_TAGS_PATH = "ways_tags.csv"

LOWER_COLON = re.compile(r'^([a-z]|_)+:([a-z]|_)+')
PROBLEMCHARS = re.compile(r'[=\+/&<>;\'"\?%#$@\,\. \t\r\n]')
street_type_re = re.compile(r'\b\S+\.?$', re.IGNORECASE)

mapping_street = { "St": "Street",
            "St.": "Street",
            "street": "Street",
            "Ave": "Avenue",
            "Ave.": "Avenue",
            "Blvd": "Boulevard",
            "Blvd.": "Boulevard",
            "Boulavard": "Boulevard",
            "Rd": "Road",
            "Rd.": "Road",
            "RD": "Road",
            "Pl": "Place",
            "Pl.": "Place",
            "PKWY": "Parkway",
            "Pkwy": "Parkway",
            "Ln": "Lane",
            "Ln.": "Lane",
            "Dr": "Drive",
            "Dr.": "Drive"
            }

mapping_phone = { "(480)331-VOIP": "480-331-8647,",
                "480-814-TOGO": "480-814-8646"
                }

SCHEMA = schema.schema

# Make sure the fields order in the csvs matches the column order in the sql table schema
NODE_FIELDS = ['id', 'lat', 'lon', 'user', 'uid', 'version', 'changeset', 'timestamp']
NODE_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_FIELDS = ['id', 'user', 'uid', 'version', 'changeset', 'timestamp']
WAY_TAGS_FIELDS = ['id', 'key', 'value', 'type']
WAY_NODES_FIELDS = ['id', 'node_id', 'position']

def fix_street_name(street_name):
    m = street_type_re.search(street_name)
    if m:
        street_type = m.group()
        if street_type in mapping_street:
            street_name = re.sub(street_type, mapping_street[street_type], street_name)
    return street_name
            
def fix_phone(number):
    if number in mapping_phone:
        number = re.sub(number, mapping_phone[number], number)
    return number
def shape_element(element, node_attr_fields=NODE_FIELDS, 
                  way_attr_fields=WAY_FIELDS, problem_chars=PROBLEMCHARS,
                  default_tag_type='regular'):
    """Clean and shape node or way XML element to Python dict"""

    node_attribs = {}
    way_attribs = {}
    way_nodes = []
    # Handle secondary tags the same way for both node and way elements
    tags = [] 

    if element.tag == 'node':
        for field in NODE_FIELDS:
            # node_attribs contains top level node attributes
            node_attribs[field] = element.attrib[field]
            
        for child in element:
            # one dictionay per secondary tag
            tag = {}
            # if tag "k" contains problematic characters, ignore it
            if PROBLEMCHARS.match(child.attrib["k"]):
                continue        
            
            elif LOWER_COLON.search(child.attrib["k"]):
                tag["id"] = element.attrib["id"]
                tag_type = child.attrib["k"].split(':',1)[0]
                tag_key = child.attrib["k"].split(':',1)[1]
                tag["key"] = tag_key
                tag["value"] = child.attrib["v"]
                if child.attrib["k"] == 'addr:street':
                        # check if function returns a value
                        if fix_street_name(child.attrib["v"]):
                            tag["value"] = fix_street_name(child.attrib["v"])
                        else:
                            continue
                    
                if (child.attrib['k'] == 'phone') or (child.attrib['k'] == 'contact:phone'):
                        # check if function returns a value
                        if fix_phone(child.attrib['v']):
                            tag['value'] = fix_phone(child.attrib['v'])
                        else:
                            continue
            
                # if this condition doesn't hold (which it never will
                # because there  is no 'tag_type' assignment in your code
                if tag_type:
                    tag["type"] = tag_type
                # then this block will execute - over-writing your previous code
                else:
                    tag["type"] = 'regular'
                    tag["id"] = element.attrib["id"]
                    tag["value"] = child.attrib["v"]
            else:
                tag["value"] = child.attrib["v"]
                tag["key"] = child.attrib["k"]
                tag["type"] = "regular"
                tag["id"] = element.attrib["id"]
            if tag:
                tags.append(tag)
        return {'node': node_attribs, 'node_tags': tags}
        
    elif element.tag == 'way':
        for field in WAY_FIELDS:
            # way holds top level way attributes
            way_attribs[field] = element.attrib[field]
              
        for child in element:
            way_nodes_dict = {}
            tag = {}
            if child.tag == 'tag':
                if PROBLEMCHARS.match(child.attrib["k"]):
                    continue  
                elif LOWER_COLON.search(child.attrib["k"]):
                    tag["id"] = element.attrib["id"]
                    tag_type = child.attrib["k"].split(':',1)[0]
                    tag_key = child.attrib["k"].split(':',1)[1]
                    tag["key"] = tag_key
                    tag["value"] = child.attrib["v"]
                    if child.attrib["k"] == 'addr:street':
                            # check if function returns a value
                            if fix_street_name(child.attrib["v"]):
                                tag["value"] = fix_street_name(child.attrib["v"])
                            else:
                                continue

                    if (child.attrib['k'] == 'phone') or (child.attrib['k'] == 'contact:phone'):
                            # check if function returns a value
                            if fix_phone(child.attrib['v']):
                                tag['value'] = fix_phone(child.attrib['v'])
                            else:
                                continue
                    if tag_type:
                        tag["type"] = tag_type
                    else:
                        tag["type"] = 'regular'
                        tag["value"] = child.attrib["v"]
                else:
                    tag["value"] = child.attrib["v"]
                    tag["key"] = child.attrib["k"]
                    tag["type"] = "regular"
                    tag["id"] = element.attrib["id"]
                if tag:
                    tags.append(tag)

            
            elif child.tag == 'nd':
                way_nodes_dict['id'] = element.attrib['id']
                way_nodes_dict['node_id'] = child.attrib['ref']
                way_nodes_dict['position'] = len(way_nodes)
            
                if way_nodes_dict:
                    way_nodes.append(way_nodes_dict) 
            else:
                continue   
        return {'way': way_attribs, 'way_nodes': way_nodes, 'way_tags': tags}

def get_element(osm_file, tags=('node', 'way', 'relation')):
    """Yield element if it is the right type of tag"""

    context = ET.iterparse(osm_file, events=('start', 'end'))
    _, root = next(context)
    for event, elem in context:
        if event == 'end' and elem.tag in tags:
            yield elem
            root.clear()


def validate_element(element, validator, schema=SCHEMA):
    """Raise ValidationError if element does not match schema"""
    if validator.validate(element, schema) is not True:
        field, errors = next(validator.errors.iteritems())
        message_string = "\nElement of type '{0}' has the following errors:\n{1}"
        error_strings = (
            "{0}: {1}".format(k, v if isinstance(v, str) else ", ".join(v))
            for k, v in errors.iteritems()
        )
        raise cerberus.ValidationError(
            message_string.format(field, "\n".join(error_strings))
        )


class UnicodeDictWriter(csv.DictWriter, object):
    """Extend csv.DictWriter to handle Unicode input"""

    def writerow(self, row):
        super(UnicodeDictWriter, self).writerow({
            k: (v.encode('utf-8') if isinstance(v, unicode) else v) for k, v in row.iteritems()
        })

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

def process_map(file_in, validate):
    """Iteratively process each XML element and write to csv(s)"""

    with codecs.open(NODES_PATH, 'w') as nodes_file, \
         codecs.open(NODE_TAGS_PATH, 'w') as nodes_tags_file, \
         codecs.open(WAYS_PATH, 'w') as ways_file, \
         codecs.open(WAY_NODES_PATH, 'w') as way_nodes_file, \
         codecs.open(WAY_TAGS_PATH, 'w') as way_tags_file:

        nodes_writer = UnicodeDictWriter(nodes_file, NODE_FIELDS)
        node_tags_writer = UnicodeDictWriter(nodes_tags_file, NODE_TAGS_FIELDS)
        ways_writer = UnicodeDictWriter(ways_file, WAY_FIELDS)
        way_nodes_writer = UnicodeDictWriter(way_nodes_file, WAY_NODES_FIELDS)
        way_tags_writer = UnicodeDictWriter(way_tags_file, WAY_TAGS_FIELDS)

        nodes_writer.writeheader()
        node_tags_writer.writeheader()
        ways_writer.writeheader()
        way_nodes_writer.writeheader()
        way_tags_writer.writeheader()

        validator = cerberus.Validator()

        for element in get_element(file_in, tags=('node', 'way')):
            el = shape_element(element)
            if el:
                if validate is True:
                    validate_element(el, validator)

                if element.tag == 'node':
                    nodes_writer.writerow(el['node'])
                    node_tags_writer.writerows(el['node_tags'])
                elif element.tag == 'way':
                    ways_writer.writerow(el['way'])
                    way_nodes_writer.writerows(el['way_nodes'])
                    way_tags_writer.writerows(el['way_tags'])

process_map(OSM_PATH, validate=True)
