from charm.toolbox.pairinggroup import PairingGroup
from charm.schemes.abenc.waters11 import Waters11 as CharmWaters11

class CPABE:
    def __init__(self, scheme_name, group_param='SS512', uni_size_param=100):
        if scheme_name.upper() == "WATERS11":
            self.groupObj = PairingGroup(group_param)
            self.scheme_instance = CharmWaters11(self.groupObj, uni_size_param)
        else:
            raise NotImplementedError(f"Scheme {scheme_name} is not supported by this CPABE wrapper.")