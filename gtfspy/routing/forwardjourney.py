from gtfspy.routing.connection import Connection


class ForwardJourney:
    """
    A class for handling journeys generated by routing algorithms
    Current assumptions:
    - legs are added in order of travel
    - walking trips do not have a trip_id
    """

    def __init__(self, legs=None):
        """
        Parameters
        ----------
        legs: list[Connection]
        """
        self.legs = []
        self.departure_time = None
        self.arrival_time = None
        self.trip_ids = set()
        self.n_boardings = 0
        if legs is not None:
            for leg in legs:
                self.add_leg(leg)

    def add_leg(self, leg):
        """
        Parameters
        ----------
        leg: Connection
        """
        assert (isinstance(leg, Connection))
        if not self.legs:
            self.departure_time = leg.departure_time
        self.arrival_time = leg.arrival_time
        if leg.trip_id and (not self.legs or (leg.trip_id != self.legs[-1].trip_id)):
            self.n_boardings += 1
        self.arrival_time = leg.arrival_time
        self.legs.append(leg)

    def get_legs(self):
        return self.legs

    def get_travel_time(self):
        travel_time = self.arrival_time - self.departure_time
        return travel_time

    def get_transfers(self):
        return max(self.n_boardings - 1, 0)

    def get_all_stops(self):
        all_stops = []
        for leg in self.legs:
            all_stops.append(leg.departure_stop)
        all_stops.append(self.legs[-1].arrival_stop)
        return all_stops

    def get_transfer_stop_pairs(self):
        """
        Get stop pairs through which transfers take place

        Returns
        -------
        transfer_stop_pairs: list
        """
        transfer_stop_pairs = []
        previous_arrival_stop = None
        current_trip_id = None
        for leg in self.legs:
            if leg.trip_id is not None and leg.trip_id != current_trip_id and previous_arrival_stop is not None:
                transfer_stop_pair = (previous_arrival_stop, leg.departure_stop)
                transfer_stop_pairs.append(transfer_stop_pair)
            previous_arrival_stop = leg.arrival_stop
            current_trip_id = leg.trip_id
        return transfer_stop_pairs

    def get_transfer_trip_pairs(self):
        pass

    def get_waiting_times(self):
        waiting_times = []
        previous_arrival = None
        for leg in self.legs:
            current_departure = leg.departure_time
            if previous_arrival:
                waiting_times.append(current_departure - previous_arrival)
            previous_arrival = leg.arrival_time
        return waiting_times

    def get_total_waiting_time(self):
        waiting_times = self.get_waiting_times()
        waiting_total = sum(waiting_times)
        return waiting_total

    def get_invehicle_times(self):
        invehicle_times = []
        for leg in self.legs:
            assert (isinstance(leg, Connection))
            if leg.trip_id is not None:
                invehicle_times.append(leg.duration())
        return invehicle_times

    def get_total_invehicle_time(self):
        return sum(self.get_invehicle_times())

    def get_walking_times(self):
        walking_times = []
        for leg in self.legs:
            if leg.is_walk:
                walking_times.append(leg.duration() - leg.waiting_time)
        return walking_times

    def get_total_walking_time(self):
        return sum(self.get_walking_times())

    def dominates(self, other, consider_time=True, consider_boardings=True):
        if consider_time:
            dominates_time = (self.departure_time >= other.departure_time and
                              self.arrival_time <= other.arrival_time)
            if not dominates_time:
                return False
        if consider_boardings:
            dominates_boardings = (self.n_boardings <= other.n_boardings)
            if not dominates_boardings:
                return False
        # dominates w.r.t all aspects:
        return True
