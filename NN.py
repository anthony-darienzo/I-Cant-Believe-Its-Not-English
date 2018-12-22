import math
import torch
import torch.nn as nn
import torch.optim as optim
from lib import support
from lib import tensorlib

class LSTM_NN(nn.Module):
    def __init__(self, input_size, interior_layer_dimensions, output_size,device=tensorlib.torch_device):
        super(LSTM_NN, self).__init__()

        self.interior_layer_dimensions = interior_layer_dimensions

        # Construct the layers of the NN
        self.lstm_cell_array = []
        for i in range(len(interior_layer_dimensions)):

            if i == 0:
                input_dimension = input_size
                output_dimension = interior_layer_dimensions[i]
            else:
                input_dimension = interior_layer_dimensions[i-1]
                output_dimension = interior_layer_dimensions[i]

            self.lstm_cell_array.append(nn.LSTMCell(input_dimension,output_dimension))

        self.final_tensor = nn.Linear(interior_layer_dimensions[-1],output_size)
        self.dropout = nn.Dropout(0.5)
        self.softmax = nn.LogSoftmax(dim=1)

        # Transfer to CUDA if desirable
        self.device = device
        for cell in self.lstm_cell_array:
            cell = cell.to(device=self.device)
        self.final_tensor = self.final_tensor.to(device=self.device)
        self.dropout = self.dropout.to(device=self.device)
        self.softmax = self.softmax.to(device=self.device)

        # Initialize training parameters and functions
        self.criterion = nn.NLLLoss().to(self.device)
        self.learning_rate = 0.0005

        self.max_sample_length = 180

    def forward(self, input, hidden_array, state_array):
        ''' It is critical that hidden_array is an array containing the hidden state of all layers of the NN '''

        if hidden_array is None or state_array is None:
            hidden_array, state_array = [],[]
            # Add code to replace the hidden_array and state_array with a zero tensor.
            for i in range(len(self.lstm_cell_array)):
                '''
                tensor = torch.Tensor(device=self.device)
                zero_tensor = tensor.new_zeros((self.interior_layer_dimensions[i]))
                hidden_array.append(zero_tensor)
                state_array.append(zero_tensor)
                '''
                hidden_array.append(None)
                state_array.append(None)

        assert len(hidden_array) == len(self.lstm_cell_array) and len(state_array) == len(self.lstm_cell_array)

        new_hidden_array = []
        new_state_array = []


        if hidden_array[0] is None or state_array[0] is None:
            initial_hidden,initial_state = self.lstm_cell_array[0](input)
        else:
            initial_hidden,initial_state = self.lstm_cell_array[0](input,(hidden_array[0],state_array[0]))
        new_hidden_array.append(initial_hidden)
        new_state_array.append(initial_state)

        # We start at 1 because the first layer was handled above
        for i in range(1,len(self.lstm_cell_array)):
            lstm_layer = self.lstm_cell_array[i]

            previous_layer_state = new_state_array[i-1]
            this_layer_hidden  = hidden_array[i]
            this_layer_state = state_array[i]

            #new_hidden, new_state = lstm_layer(previous_layer_state,(this_layer_hidden,this_layer_state))

            if this_layer_hidden is None or this_layer_state is None:
                new_hidden,new_state = lstm_layer(previous_layer_state)
            else:
                new_hidden,new_state = lstm_layer(previous_layer_state,(this_layer_hidden,this_layer_state))

            new_hidden_array.append(new_hidden)
            new_state_array.append(new_state)

        # We now pass the output of the LSTM network to the final linear tensor, then we apply a softmax and dropout.
        final_layer_output = self.final_tensor(new_state_array[-1])
        output = self.softmax(self.dropout(final_layer_output))

        return output, new_hidden_array, new_state_array

    def train(self,input_line_tensor, target_line_tensor):
        target_line_tensor.unsqueeze_(-1)

        self.zero_grad()

        output,hidden,state = None,None,None

        loss = 0

        for i in range(input_line_tensor.size(0)):
            #support.printProgress(i,i_max=input_line_tensor.size(0))
            output, hidden, state = self(input_line_tensor[i], hidden, state)

            loss += self.criterion(output,target_line_tensor[i])

        loss.backward()

        for p in self.parameters():
            p.data.add_(-self.learning_rate,p.grad.data)

        return output, loss.item() / input_line_tensor.size(0)



    def sample(self,start_letter='A'):
        with torch.no_grad():  # no need to track history in sampling
            input = tensorlib.inputTensor(start_letter)
            hidden = None
            state = None

            output_pickup = start_letter

            for i in range(self.max_sample_length):
                output, hidden,state = self(input[0], hidden,state)
                topv, topi = output.topk(1)
                topi = topi[0][0]
                if topi == support.n_letters - 1:
                    break
                else:
                    letter = support.all_letters[topi]
                    output_pickup += letter
                input = tensorlib.inputTensor(letter)

            return output_pickup
    def samples(self, start_letters='ABC'):
        for start_letter in start_letters:
            woah = self.sample(start_letter)
            print(woah)
            yield woah