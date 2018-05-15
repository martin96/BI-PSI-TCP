import socket
from enum import Enum
from collections import namedtuple


class ServerHelper:
    @staticmethod
    def generate_message(bytes_to_encode: str) -> bytes:
        return bytes(bytes_to_encode, encoding="utf-8") + b'\x07\x08'


class ServerMessages(Enum):
    SERVER_MOVE = "102 MOVE"
    SERVER_TURN_LEFT = "103 TURN LEFT"
    SERVER_TURN_RIGHT = "104 TURN RIGHT"
    SERVER_PICK_UP = "105 GET MESSAGE"
    SERVER_LOGOUT = "106 LOGOUT"
    SERVER_OK = "200 OK"
    SERVER_LOGIN_FAILED = "300 LOGIN FAILED"
    SERVER_SYNTAX_ERROR = "301 SYNTAX ERROR"
    SERVER_LOGIC_ERROR = "302 LOGIC ERROR"


class ClientMessages(Enum):
    CLIENT_RECHARGING = "RECHARGING"
    CLIENT_FULL_POWER = "FULL POWER"


class Server:
    class ServerState(Enum):
        SERVER_STARTED = 0
        SERVER_CONFIRMATION = 1
        SERVER_OK = 2
        SERVER_LOGIN_FAILED = 3
        SERVER_SYNTAX_ERROR = 4
        SERVER_MOVING = 5
        SERVER_PICK_UP_PHASE = 6

    class Robot:
        def __init__(self):
            self.facing = None
            self.name_ascii = []
            self.current_cell = None

            self.cell = namedtuple("Field", ["x", "y"])
            self.field = {}

            self.previous_cell = None
            self.vector_to_origin = None

            self.last_was_pick_up = True

            self.was_recharging = False

            for xPos in range(-2, 3):
                for yPos in range(-2, 3):
                    self.field[self.cell(x=xPos, y=yPos)] = 0

        def update_position(self, new_position: tuple):
            if self.previous_cell:
                if self.previous_cell.x == new_position[0] and self.previous_cell.y == new_position[1]:
                    return

            position_x = new_position[0]
            position_y = new_position[1]
            self.current_cell = self.cell(x=position_x, y=position_y)

            if not self.previous_cell:
                self.previous_cell = self.cell(x=position_x, y=position_y)
            elif not self.facing:
                self.facing = self.cell(x=position_x - self.previous_cell.x,
                                        y=position_y - self.previous_cell.y)

                self.vector_to_origin = self.cell(-2 - position_x, -2 - position_y)
                print("Vector to origin : " + str(self.vector_to_origin.x) + ", " + str(self.vector_to_origin.y))

        def next_move(self):
            print("My position : " + str(self.current_cell.x) + ", " + str(self.current_cell.y))

            if self.current_cell.x == -2 and self.current_cell.y == -2:
                print("Self Facing : " + str(self.facing.x) + ", " + str(self.facing.y))
                if self.facing.x == 0 and self.facing.y == 1:
                    self.field[self.cell(x=-2, y=-2)] = 1
                    return 10
                else:
                    self.facing = self.cell(x=self.facing.y, y=-self.facing.x)
                    return 2

            next_move_current_facing = self.cell(x=self.current_cell.x + self.facing.x,
                                                 y=self.current_cell.y + self.facing.y)

            if (abs(-2 - next_move_current_facing.x) + abs(-2 - next_move_current_facing.y)) \
                    < abs(-2 - self.current_cell.x) + abs(-2 - self.current_cell.y):
                return 1
            else:
                print(self.facing)
                self.facing = self.cell(x=self.facing.y, y=-self.facing.x)
                print(self.facing)
                return 2

        def next_move_in_field(self):
            next_move_current_facing = self.cell(x=self.current_cell.x + self.facing.x,
                                                 y=self.current_cell.y + self.facing.y)

            if next_move_current_facing in self.field and self.field[
                            self.cell(x=next_move_current_facing.x, y=next_move_current_facing.y)] == 0:
                self.field[self.cell(x=next_move_current_facing.x, y=next_move_current_facing.y)] = 1
                self.current_cell = next_move_current_facing
                return 1
            else:
                self.facing = self.cell(x=self.facing.y, y=-self.facing.x)
                return 2

    def __init__(self):
        self.TCP_IP = '127.0.0.1'
        self.TCP_PORT = 3999
        self.BUFFER_SIZE = 16

        self.SERVER_KEY = 54621
        self.CLIENT_KEY = 45328

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.TCP_IP, self.TCP_PORT))
        self.socket.listen(1)

        self.connection, self.address = None, None

        self.dataBuffer = None
        self.state = None

        self.robot = None
        self.immediate_robot_name = None
        self.immediate_client_confirmation = None
        self.immediate_position_message = None

        self.states = {
            self.ServerState.SERVER_STARTED: self.server_confirm_name,
            self.ServerState.SERVER_CONFIRMATION: self.server_ok_or_login_failed,
            self.ServerState.SERVER_OK: self.server_move,
            self.ServerState.SERVER_LOGIN_FAILED: self.server_failed,
            self.ServerState.SERVER_SYNTAX_ERROR: self.server_syntax_error,
            self.ServerState.SERVER_MOVING: self.server_moving,
            self.ServerState.SERVER_PICK_UP_PHASE: self.server_pick_up
        }

    def start_receiving(self):
        self.connection, self.address = self.socket.accept()
        self.connection.settimeout(2)

        self.dataBuffer = bytearray()
        self.state = self.ServerState.SERVER_STARTED

        self.robot = self.Robot()
        self.immediate_robot_name = None
        self.immediate_client_confirmation = None
        self.immediate_position_message = None

        while True:
            try:
                data = self.connection.recv(self.BUFFER_SIZE)
            except socket.timeout:
                print("GOT TIMEOUT")
                server.close_connection()
                server.start_receiving()
                return None

            print("Received data : {}".format(data))
            print(self.dataBuffer)
            self.dataBuffer += data

            print(self.dataBuffer)
            print(self.dataBuffer.split(b'\x07\x08'))

            if self.dataBuffer[-2:] == b'\x07\x08':
                buffer_split = self.dataBuffer[:-2].split(b'\x07\x08')

                if self.robot.was_recharging:
                    if buffer_split[0].decode("utf-8") != ClientMessages.CLIENT_FULL_POWER.value:
                        self.server_logic_error()
                    else:
                        self.robot.was_recharging = False
                        self.dataBuffer.clear()
                        self.connection.settimeout(2)
                        continue

                if buffer_split[0].decode("utf-8") == ClientMessages.CLIENT_RECHARGING.value:
                    self.robot.was_recharging = True
                    self.dataBuffer.clear()
                    self.connection.settimeout(5)
                    return

                if len(buffer_split) == 2:
                    if self.state == self.ServerState.SERVER_STARTED:
                        self.immediate_client_confirmation = buffer_split[1].decode("utf-8")
                    elif self.state == self.ServerState.SERVER_CONFIRMATION:
                        self.immediate_position_message = buffer_split[1].decode("utf-8")
                elif len(buffer_split) == 3:
                    self.immediate_client_confirmation = buffer_split[1].decode("utf-8")
                    self.immediate_position_message = buffer_split[2].decode("utf-8")

                self.states[self.state](buffer_split[0].decode("utf-8"))
                self.dataBuffer.clear()
            elif b'\x07\x08' in self.dataBuffer:
                buffer_split = self.dataBuffer.split(b'\x07\x08')

                if self.robot.was_recharging:
                    if buffer_split[0].decode("utf-8") != ClientMessages.CLIENT_FULL_POWER.value:
                        self.server_logic_error()
                    else:
                        self.robot.was_recharging = False

                        del buffer_split[0]

                        new_buffer = bytearray()
                        for position in range(0, len(buffer_split)):
                            print("position: " + str(position))
                            print("len: " + str(len(buffer_split)))
                            if position + 1 != len(buffer_split):
                                new_buffer += b'\x07\x08'
                            new_buffer += buffer_split[position]

                        print(new_buffer)
                        self.dataBuffer = new_buffer

                        self.connection.settimeout(2)
                        continue

                if buffer_split[0].decode("utf-8") == ClientMessages.CLIENT_RECHARGING.value:
                    self.robot.was_recharging = True
                    self.dataBuffer.clear()
                    self.connection.settimeout(5)
                    return

                if self.state == self.ServerState.SERVER_STARTED:
                    self.immediate_robot_name = buffer_split[0]
                    self.server_confirm_name(buffer_split[0].decode("utf-8"))
                elif self.state == self.ServerState.SERVER_CONFIRMATION:
                    self.immediate_client_confirmation = buffer_split[0]
                    self.server_ok_or_login_failed(buffer_split[0].decode("utf-8"))
                elif self.state == self.ServerState.SERVER_MOVING:
                    self.immediate_position_message = buffer_split[0]
                    self.server_moving(buffer_split[0].decode("utf-8"))

                del buffer_split[0]

                new_buffer = bytearray()
                for position in range(0, len(buffer_split)):
                    print("position: " + str(position))
                    print("len: " + str(len(buffer_split)))
                    if position + 1 != len(buffer_split):
                        new_buffer += b'\x07\x08'
                    new_buffer += buffer_split[position]

                print(new_buffer)
                self.dataBuffer = new_buffer
            elif b'RECHARGING\x07' in self.dataBuffer:
                continue

            if self.state == self.ServerState.SERVER_STARTED and len(self.dataBuffer) > 10:
                self.server_syntax_error()

            if self.state == self.ServerState.SERVER_PICK_UP_PHASE and len(self.dataBuffer) > 98:
                self.server_syntax_error()

            if self.state == self.ServerState.SERVER_MOVING and len(self.dataBuffer) > 10:
                self.server_syntax_error()

    def close_connection(self):
        self.connection.close()

    def server_confirm_name(self, robot_name: str):
        if len(robot_name) > 10:
            self.server_syntax_error()
            return

        self.state = self.ServerState.SERVER_CONFIRMATION
        print(robot_name)

        self.robot.name_ascii = [ord(c) for c in robot_name]
        print(self.robot.name_ascii)
        print(self.robot.name_ascii[0:10])

        hash_code = (1000 * sum(self.robot.name_ascii)) % 65536
        confirmation_code = (hash_code + self.SERVER_KEY) % 65536

        print(confirmation_code)

        confirmation_code_in_bytes = ServerHelper.generate_message(str(confirmation_code))

        self.connection.send(confirmation_code_in_bytes)

        if self.immediate_client_confirmation is not None:
            self.server_ok_or_login_failed(self.immediate_client_confirmation)

    def server_ok_or_login_failed(self, client_confirmation: str):
        if len(client_confirmation) > 5 or not client_confirmation.isdigit():
            self.server_syntax_error()
            # return

        hash_code = (1000 * sum(self.robot.name_ascii)) % 65536
        client_confirmation_code = (hash_code + self.CLIENT_KEY) % 65536

        print("Client confirmation : " + str(
            client_confirmation_code) + ", Received confirmation : " + client_confirmation)

        if str(client_confirmation_code) == client_confirmation:
            self.state = self.ServerState.SERVER_OK
            self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_OK.value))

            if self.immediate_position_message is not None:
                self.server_moving(self.immediate_position_message)

            self.state = self.ServerState.SERVER_MOVING
            self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_MOVE.value))
        else:
            self.state = self.ServerState.SERVER_LOGIN_FAILED
            self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_LOGIN_FAILED.value))
            server.close_connection()
            server.start_receiving()

        print(self.state)

    def server_moving(self, position_message):
        message_split = position_message.split()
        print(message_split)

        try:
            int(message_split[1])
            int(message_split[2])
        except ValueError:
            self.server_syntax_error()
            return None

        if position_message[-1] == ' ':
            self.server_syntax_error()
            return

        if message_split[0] != "OK":
            self.server_syntax_error()
            return

        self.robot.update_position((int(message_split[1]), int(message_split[2])))
        if not self.robot.facing:
            self.server_move()
        else:
            next_move = self.robot.next_move()
            if next_move == 1:
                self.server_move()
            elif next_move == 2:
                self.server_turn_right()
            elif next_move == 10:
                self.state = self.ServerState.SERVER_PICK_UP_PHASE
                self.server_start_pick_up()

    def server_move(self):
        self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_MOVE.value))

    def server_turn_right(self):
        self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_TURN_RIGHT.value))

    def server_start_pick_up(self):
        self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_PICK_UP.value))

    def server_pick_up(self, message):
        if self.robot.last_was_pick_up:
            if message:
                print("Message: " + message)
                self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_LOGOUT.value))
                server.close_connection()
                server.start_receiving()
            else:
                self.robot.last_was_pick_up = False
                next_move = self.robot.next_move_in_field()
                if next_move == 1:
                    self.server_move()
                elif next_move == 2:
                    self.server_turn_right()
        else:
            print("Message: " + message)
            message_split = message.split()

            try:
                int(message_split[1])
                int(message_split[2])
            except ValueError:
                self.server_syntax_error()
                return None

            if message[-1] == ' ':
                self.server_syntax_error()
                return

            if message_split[0] != "OK":
                self.server_syntax_error()
                return

            if self.robot.previous_cell:
                if self.robot.current_cell.x != (int(message_split[1])) or self.robot.current_cell.y != (
                                int(message_split[2])):
                    self.server_move()
                    return

            self.robot.last_was_pick_up = True
            self.server_start_pick_up()

    def server_failed(self):
        pass

    def server_syntax_error(self):
        self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_SYNTAX_ERROR.value))
        server.close_connection()
        server.start_receiving()

    def server_logic_error(self):
        self.connection.send(ServerHelper.generate_message(ServerMessages.SERVER_LOGIC_ERROR.value))
        server.close_connection()
        server.start_receiving()


server = Server()
server.start_receiving()
