import os
import subprocess
from pathlib import Path

import grpc
import node_pb2 as nodepb
import pytest
from fixtures import TEST_NETWORK
from fixtures import *  # noqa: F401,F403
from node_pb2_grpc import NodeStub
from pyln.testing.utils import env

# Skip the entire module if we don't have Rust.
pytestmark = pytest.mark.skipif(
    env('RUST') != '1',
    reason='RUST is not enabled, skipping rust-dependent tests'
)

os.environ["RUST_LOG"] = "trace"


def test_rpc_client(node_factory):
    l1 = node_factory.get_node()
    bin_path = Path.cwd() / "target" / "debug" / "examples" / "cln-rpc-getinfo"
    rpc_path = Path(l1.daemon.lightning_dir) / TEST_NETWORK / "lightning-rpc"
    out = subprocess.check_output([bin_path, rpc_path], stderr=subprocess.STDOUT)
    assert(b'0266e4598d1d3c415f572a8488830b60f7e744ed9235eb0b1ba93283b315c03518' in out)


def test_grpc_connect(node_factory):
    """Attempts to connect to the grpc interface and call getinfo"""
    bin_path = Path.cwd() / "target" / "debug" / "grpc-plugin"
    l1 = node_factory.get_node(options={"plugin": str(bin_path)})

    p = Path(l1.daemon.lightning_dir) / TEST_NETWORK
    cert_path = p / "client.pem"
    key_path = p / "client-key.pem"
    ca_cert_path = p / "ca.pem"
    creds = grpc.ssl_channel_credentials(
        root_certificates=ca_cert_path.open('rb').read(),
        private_key=key_path.open('rb').read(),
        certificate_chain=cert_path.open('rb').read()
    )

    channel = grpc.secure_channel(
        "localhost:50051",
        creds,
        options=(('grpc.ssl_target_name_override', 'cln'),)
    )
    stub = NodeStub(channel)

    response = stub.Getinfo(nodepb.GetinfoRequest())
    print(response)

    response = stub.ListFunds(nodepb.ListfundsRequest())
    print(response)


def test_grpc_generate_certificate(node_factory):
    """Test whether we correctly generate the certificates.

     - If we have no certs, we need to generate them all
     - If we have certs, we they should just get loaded
     - If we delete one cert or its key it should get regenerated.
    """
    bin_path = Path.cwd() / "target" / "debug" / "grpc-plugin"
    l1 = node_factory.get_node(options={
        "plugin": str(bin_path),
    }, start=False)

    p = Path(l1.daemon.lightning_dir) / TEST_NETWORK
    files = [p / f for f in [
        'ca.pem',
        'ca-key.pem',
        'client.pem',
        'client-key.pem',
        'server-key.pem',
        'server.pem',
    ]]

    # Before starting no files exist.
    assert [f.exists() for f in files] == [False]*len(files)

    l1.start()
    assert [f.exists() for f in files] == [True]*len(files)

    # The files exist, restarting should not change them
    contents = [f.open().read() for f in files]
    l1.restart()
    assert contents == [f.open().read() for f in files]

    # Now we delete the last file, we should regenerate it as well as its key
    files[-1].unlink()
    l1.restart()
    assert contents[-2] != files[-2].open().read()
    assert contents[-1] != files[-1].open().read()


def test_grpc_wrong_auth(node_factory):
    """An mTLS client certificate should only be usable with its node

    We create two instances, each generates its own certs and keys,
    and then we try to cross the wires.
    """
    bin_path = Path.cwd() / "target" / "debug" / "grpc-plugin"
    l1, l2 = node_factory.get_nodes(2, opts={"plugin": str(bin_path), "start": False})
    l1.start()

    def connect(node):
        p = Path(node.daemon.lightning_dir) / TEST_NETWORK
        cert, key, ca = [f.open('rb').read() for f in [
            p / 'client.pem',
            p / 'client-key.pem',
            p / "ca.pem"]]

        creds = grpc.ssl_channel_credentials(
            root_certificates=ca,
            private_key=key,
            certificate_chain=cert,
        )

        channel = grpc.secure_channel(
            "localhost:50051",
            creds,
            options=(('grpc.ssl_target_name_override', 'cln'),)
        )
        return NodeStub(channel)

    stub = connect(l1)
    # This should work, it's the correct node
    stub.Getinfo(nodepb.GetinfoRequest())

    l1.stop()
    l2.start()

    # This should not work, it's a different node
    with pytest.raises(Exception, match=r'Socket closed'):
        stub.Getinfo(nodepb.GetinfoRequest())

    # Now load the correct ones and we should be good to go
    stub = connect(l2)
    stub.Getinfo(nodepb.GetinfoRequest())
