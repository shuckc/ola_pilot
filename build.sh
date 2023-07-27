python3 -m grpc_tools.protoc -I. --python_betterproto_out=. ../ola/common/rpc/Rpc.proto --proto_path=../ola/common
python3 -m grpc_tools.protoc -I. --python_betterproto_out=. ../ola/common/protocol/Ola.proto --proto_path=../ola/common

