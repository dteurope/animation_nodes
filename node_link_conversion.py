import bpy
from . import tree_info
from mathutils import Vector
from . sockets.info import toBaseIdName
from . tree_info import getAllDataLinks, getDirectlyLinkedSocket

def correctForbiddenNodeLinks():
    dataLinks = getAllDataLinks()
    invalidLinks = filterInvalidLinks(dataLinks)
    for dataOrigin, target in invalidLinks:
        nodeTree = target.nodeTree
        directOrigin = getDirectlyLinkedSocket(target)
        if not tryToCorrectLink(dataOrigin, directOrigin, target):
            removeLink(directOrigin, target)
    tree_info.updateIfNecessary()

def filterInvalidLinks(dataLinks):
    return [dataLink for dataLink in dataLinks if not isConnectionValid(*dataLink)]

def isConnectionValid(origin, target):
    return origin.dataType in target.allowedInputTypes or target.allowedInputTypes[0] == "all"

def tryToCorrectLink(dataOrigin, directOrigin, target):
    for corrector in linkCorrectors:
        if corrector.check(dataOrigin, target):
            nodeTree = target.nodeTree
            corrector.insert(nodeTree, directOrigin, target, dataOrigin)
            return True
    return False

def removeLink(origin, target):
    nodeTree = origin.nodeTree
    for link in nodeTree.links:
        if link.from_socket == origin and link.to_socket == target:
            nodeTree.links.remove(link)


class LinkCorrection:
    # subclasses need a check and insert function
    pass

class ConvertParticleSystemToParticle(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Particle System" and target.dataType == "Particle"
    def insert(self, nodeTree, origin, target, dataOrigin):
        systemInfo, listElement = insertNodes(nodeTree, ["an_GetParticlesNode", "an_GetListElementNode"], origin, target)
        listElement.generateSockets(listIdName = "an_ParticleListSocketNode")
        nodeTree.links.new(systemInfo.inputs[0], origin)
        nodeTree.links.new(listElement.inputs[0], systemInfo.outputs[0])
        nodeTree.links.new(listElement.outputs[0], target)

class ConvertParticleSystemToParticles(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Particle System" and target.dataType == "Particle List"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_GetParticlesNode", origin, target)

class ConvertListToElement(LinkCorrection):
    def check(self, origin, target):
        return toBaseIdName(origin.bl_idname) == target.bl_idname
    def insert(self, nodeTree, origin, target, dataOrigin):
        node = insertNode(nodeTree, "an_GetListElementNode", origin, target)
        node.assignType(target.dataType)
        insertBasicLinking(nodeTree, origin, node, target)

class ConvertElementToList(LinkCorrection):
    def check(self, origin, target):
        return origin.bl_idname == toBaseIdName(target.bl_idname)
    def insert(self, nodeTree, origin, target, dataOrigin):
        node = insertNode(nodeTree, "an_CreateListNode", origin, target)
        node.assignBaseDataType(origin.dataType, inputAmount = 1)
        insertBasicLinking(nodeTree, origin, node, target)

class ConvertMeshDataToMesh(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Mesh Data" and target.dataType == "Mesh"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_CreateBMeshFromMeshData", origin, target)

class ConvertMeshDataToVertexLocations(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Mesh Data" and target.dataType == "Vector List"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_SeparateMeshDataNode", origin, target)

class ConvertVertexLocationsToMeshData(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Vector List" and target.dataType == "Mesh Data"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_CombineMeshDataNode", origin, target)

class ConvertPolygonListIndicesToEdgeListIndices(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Polygon Indices List" and target.dataType == "Edge Indices List"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_EdgesOfPolygonsNode", origin, target)

class ConvertSeparatedMathDataToMesh(LinkCorrection):
    separatedMeshDataTypes = ["Vector List", "Edge Indices List", "Polygon Indices List"]
    def check(self, origin, target):
        return origin.dataType in self.separatedMeshDataTypes and target.dataType == "Mesh"
    def insert(self, nodeTree, origin, target, dataOrigin):
        toMeshData, toMesh = insertNodes(nodeTree, ["an_CombineMeshDataNode", "an_CreateBMeshFromMeshData"], origin, target)
        nodeTree.links.new(toMeshData.inputs[self.separatedMeshDataTypes.index(origin.dataType)], origin)
        nodeTree.links.new(toMesh.inputs[0], toMeshData.outputs[0])
        nodeTree.links.new(toMesh.outputs[0], target)

class ConvertToVector(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType in ["Integer", "Float"] and target.dataType == "Vector"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_CombineVectorNode", origin, target)

class ConvertVectorToNumber(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Vector" and target.dataType == "Float"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_SeparateVectorNode", origin, target)

class ConvertTextBlockToString(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Text Block" and target.dataType == "String"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_TextBlockReaderNode", origin, target)

class ConvertVectorToMatrix(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Vector" and target.dataType == "Matrix"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_TranslationMatrixNode", origin, target)

class ConvertListToLength(LinkCorrection):
    def check(self, origin, target):
        return "List" in origin.dataType and target.dataType == "Integer"
    def insert(self, nodeTree, origin, target, dataOrigin):
        insertLinkedNode(nodeTree, "an_GetListLengthNode", origin, target)

class ConverFloatToInteger(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Float" and target.dataType == "Integer"
    def insert(self, nodeTree, origin, target, dataOrigin):
        node = insertLinkedNode(nodeTree, "an_FloatToIntegerNode", origin, target)

class ConvertToBasicTypes(LinkCorrection):
    def check(self, origin, target):
        return target.dataType in ["String", "Integer", "Float"]
    def insert(self, nodeTree, origin, target, dataOrigin):
        node = insertLinkedNode(nodeTree, "an_ConvertNode", origin, target)
        tree_info.update()
        node.assignType(target.dataType)

class ConvertFromGeneric(LinkCorrection):
    def check(self, origin, target):
        return origin.dataType == "Generic"
    def insert(self, nodeTree, origin, target, dataOrigin):
        node = insertLinkedNode(nodeTree, "an_ConvertNode", origin, target)
        tree_info.update()
        node.assignType(target.dataType)


def insertLinkedNode(nodeTree, nodeType, origin, target):
    node = insertNode(nodeTree, nodeType, origin, target)
    insertBasicLinking(nodeTree, origin, node, target)
    return node

def insertNode(nodeTree, nodeType, leftSocket, rightSocket):
    nodes = insertNodes(nodeTree, [nodeType], leftSocket, rightSocket)
    return nodes[0]

def insertNodes(nodeTree, nodeTypes, leftSocket, rightSocket):
    center = getSocketCenter(leftSocket, rightSocket)
    amount = len(nodeTypes)
    nodes = []
    for i, nodeType in enumerate(nodeTypes):
        node = nodeTree.nodes.new(nodeType)
        node.select = False
        node.location = center + Vector((180 * (i - (amount - 1) / 2), 0))
        nodes.append(node)
    return nodes

def insertBasicLinking(nodeTree, originSocket, node, targetSocket):
    nodeTree.links.new(node.inputs[0], originSocket)
    nodeTree.links.new(targetSocket, node.outputs[0])

def getSocketCenter(socket1, socket2):
    return (socket1.node.location + socket2.node.location) / 2

linkCorrectors = [
    ConvertParticleSystemToParticle(),
    ConvertParticleSystemToParticles(),
    ConvertListToElement(),
    ConvertElementToList(),
    ConvertMeshDataToMesh(),
    ConvertMeshDataToVertexLocations(),
    ConvertVertexLocationsToMeshData(),
    ConvertPolygonListIndicesToEdgeListIndices(),
    ConvertSeparatedMathDataToMesh(),
    ConvertToVector(),
    ConvertVectorToNumber(),
    ConvertTextBlockToString(),
    ConvertVectorToMatrix(),
	ConvertListToLength(),
    ConverFloatToInteger(),
    ConvertToBasicTypes(),
    ConvertFromGeneric() ]
