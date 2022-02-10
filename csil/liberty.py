import liberty
from liberty.parser import parse_liberty

lib_cache = {}

# Process a liberty library down to a dict of cell names and areas
def make_lib(fname):
    if fname in lib_cache:
        return lib_cache[fname]

    try:
        libr = parse_liberty(open(fname).read())
    except:
        print(f"Error parsing liberty library {fname}")
        return None
    
    nm2area = {}
    for cell in libr.get_groups("cell"):
        name = cell.args[0]
        if type(cell.args[0]) == liberty.types.EscapedString:
            name = cell.args[0].value
        nm2area[name] = cell.attributes["area"]
    del libr
    lib_cache[fname] = nm2area
    return nm2area

