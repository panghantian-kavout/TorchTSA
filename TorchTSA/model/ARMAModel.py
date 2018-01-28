import logging
import typing

import numpy as np
import torch
import torch.optim as optim
from torch.autograd import Variable
from torch.distributions import Normal


class ARMAModel:

    def __init__(
            self,
            _phi_num: int = 1,
            _theta_num: int = 1,
            _use_const: bool = True
    ):
        assert _phi_num >= 0
        assert _theta_num >= 0
        assert _phi_num + _theta_num > 0

        # fitter params
        self.phi_num = _phi_num  # len of phi_arr
        self.theta_num = _theta_num  # len of theta_arr
        self.use_const = _use_const

        # model params
        self.phi_arr: np.ndarray = np.zeros(self.phi_num)
        self.theta_arr: np.ndarray = np.zeros(self.theta_num)
        self.const_arr: np.ndarray = None
        self.log_sigma_arr: np.ndarray = None

        # latent for MA part
        self.latent_arr: np.ndarray = None

    @staticmethod
    def stack_delay_arr(
            _arr: typing.Sequence[float], _num: int
    ) -> np.ndarray:
        ret_list = []
        for i in range(_num):
            shift = i + 1
            ret_list.append(_arr[_num - shift: -shift])
        return np.stack(ret_list)

    def fit(
            self, _arr: typing.Sequence[float],
            _max_iter: int = 20,
    ):
        assert len(_arr) > self.phi_num
        assert len(_arr) > self.theta_num

        # y_var
        arr = np.array(_arr)
        y_var = Variable(
            torch.from_numpy(arr[self.phi_num:]).float()
        )

        if self.phi_num > 0:
            # ar_x_var
            ar_x_arr = self.stack_delay_arr(arr, self.phi_num)
            ar_x_var = Variable(torch.from_numpy(ar_x_arr).float())

        # get vars and optimizer
        params = []
        # 1. const
        if self.const_arr is None:
            if self.use_const:
                self.const_arr = np.mean(arr, keepdims=True)
            else:
                self.const_arr = np.zeros(1)
        if self.use_const:
            const_var = Variable(
                torch.from_numpy(self.const_arr).float(),
                requires_grad=True
            )
            params.append(const_var)
        else:
            const_var = Variable(
                torch.from_numpy(self.const_arr).float()
            )
        # 2. sigma
        if self.log_sigma_arr is None:
            self.log_sigma_arr = np.log([np.std(arr, keepdims=True)])
        log_sigma_var = Variable(
            torch.from_numpy(self.log_sigma_arr).float(),
            requires_grad=True
        )
        params.append(log_sigma_var)
        # 3. phi
        if self.phi_num > 0:
            phi_var = Variable(
                torch.from_numpy(self.phi_arr).float().unsqueeze(0),
                requires_grad=True
            )
            params.append(phi_var)
        # 4. theta
        if self.theta_num > 0:
            theta_var = Variable(
                torch.from_numpy(self.theta_arr).float().unsqueeze(0),
                requires_grad=True
            )
            params.append(theta_var)

        optimizer = optim.LBFGS(params, max_iter=_max_iter)

        # init latent arr
        self.latent_arr = np.zeros(
            len(arr) + self.theta_num - self.phi_num
        )

        def closure():
            if self.theta_num > 0:
                # update latent var
                tmp_arr = arr[self.phi_num:] - const_var.data.numpy()
                tmp_arr = tmp_arr - theta_var.data.numpy().dot(
                    self.stack_delay_arr(self.latent_arr, self.theta_num)
                )
                if self.phi_num > 0:
                    tmp_arr = tmp_arr - phi_var.data.numpy().dot(ar_x_arr)
                self.latent_arr[self.theta_num:] = tmp_arr
                # ma_x_var
                ma_x_arr = self.stack_delay_arr(self.latent_arr, self.theta_num)
                ma_x_var = Variable(torch.from_numpy(ma_x_arr).float())
            # loss
            optimizer.zero_grad()
            out = y_var - const_var
            if self.phi_num > 0:
                out = out - torch.mm(phi_var, ar_x_var)
            if self.theta_num > 0:
                out = out - torch.mm(theta_var, ma_x_var)
            loss = -Normal(
                0, torch.exp(log_sigma_var)
            ).log_prob(out).mean()
            logging.info('loss: {}'.format(loss.data.numpy()[0]))
            loss.backward()
            return loss

        optimizer.step(closure)

        # update array
        if self.use_const:
            self.const_arr = const_var.data.numpy()
        self.log_sigma_arr = log_sigma_var.data.numpy()
        if self.phi_num > 0:
            self.phi_arr = phi_var.data.numpy()[0]
        if self.theta_num > 0:
            self.theta_arr = theta_var.data.numpy()[0]

    def predict(
            self,
            _arr: typing.Sequence[float],
            _latent: typing.Sequence[float] = None,
    ) -> float:
        arr = np.array(_arr)
        if _latent is None:
            latent = self.latent_arr
        else:
            latent = np.array(_latent)
        value = self.const_arr[0]
        if self.phi_num > 0:
            tmp_arr = arr[-self.phi_num:]
            tmp_arr = tmp_arr[::-1]
            value += (tmp_arr * self.phi_arr).sum()
        if self.theta_num > 0:
            tmp_latent = latent[-self.theta_num:]
            tmp_latent = tmp_latent[::-1]
            value += (tmp_latent * self.theta_arr).sum()

        return value

    def getPhis(self) -> np.ndarray:
        return self.phi_arr

    def getThetas(self) -> np.ndarray:
        return self.theta_arr

    def getConst(self) -> np.ndarray:
        return self.const_arr

    def getSigma(self) -> np.ndarray:
        return np.exp(self.log_sigma_arr)
