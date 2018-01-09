import logging

import pyflux as pf

from TorchTSA.model import ARModel
from TorchTSA.simulate import ARSim

logging.basicConfig(level=logging.INFO)

# simulate data
ar_sim = ARSim(_theta_arr=[0.3, -0.2], _const=0.0)
sim_data = ar_sim.sample_n(1000)

ar_model = ARModel(_theta_num=2, _use_const=True)
ar_model.fit(sim_data)
print(ar_model.getThetas(), ar_model.getConst(), ar_model.getSigma())
print(ar_model.predict(sim_data))

pf_model = pf.ARIMA(data=sim_data, ar=2, ma=0, integ=0)
pf_ret = pf_model.fit("MLE")
pf_ret.summary()
