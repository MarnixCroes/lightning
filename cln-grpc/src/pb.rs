tonic::include_proto!("cln");

use cln_rpc::primitives::Amount as JAmount;

impl From<JAmount> for Amount {
    fn from(a: JAmount) -> Self {
        match a {
            JAmount::Millisatoshi(v) => Amount {
                unit: Some(amount::Unit::Millisatoshi(v)),
            },
            JAmount::Satoshi(v) => Amount {
                unit: Some(amount::Unit::Satoshi(v)),
            },
            JAmount::Millibitcoin(v) => Amount {
                unit: Some(amount::Unit::Satoshi(v * 100_000)),
            },
            JAmount::Bitcoin(v) => Amount {
                unit: Some(amount::Unit::Bitcoin(v)),
            },
        }
    }
}

impl From<&Amount> for JAmount {
    fn from(a: &Amount) -> Self {
        match a {
            Amount {
                unit: Some(amount::Unit::Millisatoshi(v)),
            } => JAmount::Millisatoshi(*v),
            Amount {
                unit: Some(amount::Unit::Satoshi(v)),
            } => JAmount::Satoshi(*v),
            Amount {
                unit: Some(amount::Unit::Bitcoin(v)),
            } => JAmount::Bitcoin(*v),
	    o => panic!("Unhandled conversion from pb:Amount to json:Amount: {:?}", o),
        }
    }
}
