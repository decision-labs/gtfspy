from collections import namedtuple

import datetime
import numpy as np
import pandas as pd
from matplotlib import animation
from matplotlib import pyplot as plt

from gtfspy.route_types import ROUTE_TYPE_TO_COLOR

PlotConnection = namedtuple('PlotConnection', 'route_type from_lat from_lon to_lat to_lon departure_time arrival_time')


class JourneyAnimator:

    def __init__(self, journey_labels, G, spatial_bounds=None, tail_seconds=120, journey_markers=True):
        """
        Parameters
        ----------
        journey_labels: list[gtfspy.routing.label]
        G: gtfspy.gtfs.GTFS
        spatial_bounds: dict, optional
        tail_seconds: int
        journey_markers: bool
        """
        self.__anim_ax = None
        self.tail_seconds = tail_seconds
        self.path_markers = journey_markers
        self.plot_journeys = self.__get_coordinate_augmented_connections_from_labels(journey_labels, G)
        if spatial_bounds is None:
            from_lats = [pc.from_lat for journey in self.plot_journeys for pc in journey]
            to_lats = [pc.to_lat for journey in self.plot_journeys for pc in journey]
            from_lons = [pc.from_lon for journey in self.plot_journeys for pc in journey]
            to_lons = [pc.to_lon for journey in self.plot_journeys for pc in journey]
            min_lat = min((min(from_lats), min(to_lats)))
            max_lat = max((max(from_lats), max(to_lats)))
            min_lon = min((min(from_lons), min(to_lons)))
            max_lon = max((max(from_lons), max(to_lons)))
            lat_buffer = (max_lat - min_lat) * 0.1
            lon_buffer = (max_lon - min_lon) * 0.1
            self.spatial_bounds = {"lat_min": min_lat - lat_buffer,
                                   "lat_max": max_lat + lat_buffer,
                                   "lon_max": max_lon + lon_buffer,
                                   "lon_min": min_lon - lon_buffer}
        else:
            self.spatial_bounds = spatial_bounds

    @staticmethod
    def __get_coordinate_augmented_connections_from_labels(journey_labels, G):
        """
        Expand labels into connection lists and augment each connection with coordinates.

        Return
        ------
        list[list[PlotJourney]]
        """
        # Two helper dicts:
        stopI_to_pos = {}
        for i, row in pd.read_sql("SELECT * FROM stops", G.conn).iterrows():
            stopI_to_pos[row['stop_I']] = {'lat': row['lat'], 'lon': row['lon']}

        trip_I_to_route_type = {}
        for i, row in pd.read_sql("SELECT trips.trip_I as trip_I, routes.type as route_type "
                                  "FROM trips LEFT JOIN routes "
                                  "ON trips.route_I=routes.route_I", G.conn).iterrows():
            trip_I_to_route_type[row['trip_I']] = row['route_type']
        trip_I_to_route_type[-1] = -1

        # Do the actual mapping:
        plot_journeys = []
        for label in journey_labels:
            plot_connections = []
            cur_label = label
            while cur_label:
                cur_conn = cur_label.connection
                pc = PlotConnection(trip_I_to_route_type[cur_conn.trip_id],
                                    stopI_to_pos[cur_conn.departure_stop]['lat'],
                                    stopI_to_pos[cur_conn.departure_stop]['lon'],
                                    stopI_to_pos[cur_conn.arrival_stop]['lat'],
                                    stopI_to_pos[cur_conn.arrival_stop]['lon'],
                                    cur_conn.departure_time,
                                    cur_conn.arrival_time)
                plot_connections.append(pc)
                if hasattr(cur_label, "previous_label") and cur_label.previous_label:
                    cur_label = cur_label.previous_label
                else:
                    cur_label = None
            plot_journeys.append(plot_connections)
        return plot_journeys

    def snapshot(self, time_ut, ax=None):
        """
        Parameters
        ----------
        time_ut: int
        ax: matplotlib.axes.Axes, optional

        Return
        ------
        ax: matplotlib.axes.Axes
        """
        if ax is None:
            fig = plt.figure()
            ax = fig.add_subplot(111, projection="smopy_axes")
            ax.set_map_bounds(**self.spatial_bounds)
            ax.set_plot_bounds(**self.spatial_bounds)
        self.__plot_paths(ax, self.plot_journeys, time_ut)

        time_str = datetime.datetime.fromtimestamp(time_ut).strftime('%Y-%m-%d %H:%M:%S')
        ax.set_title(time_str)

    def animation(self, fps=5, anim_length_seconds=20):
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="smopy_axes")
        ax.set_map_bounds(**self.spatial_bounds)
        ax.set_plot_bounds(**self.spatial_bounds)

        start_time_ut = min(
            c.departure_time for journey_path in self.plot_journeys for c in journey_path) - self.tail_seconds - 1
        end_time_ut = max(c.arrival_time for path in self.plot_journeys for c in path) + self.tail_seconds + 1

        n_frames = fps * anim_length_seconds

        ani = animation.FuncAnimation(fig,
                                      self.__animation_frame,
                                      frames=np.linspace(start_time_ut, end_time_ut, num=n_frames),
                                      fargs=(ax,),
                                      interval=1. / fps * 1000)
        return ani

    def __animation_frame(self, time_ut, ax):
        ax.lines = []
        ax.texts = []
        ax.collections = []
        ax.prev_texts = []
        ax.prev_plots = []
        ax.prev_scatters = []
        self.snapshot(time_ut, ax)

    def __plot_paths(self, ax, paths, time_ut):
        """
        Plot the given paths at

        Parameters
        ----------
        ax: matplotlib.axes.Axes
        paths: list[list[PlotConnection]]
        time_ut: int
        """
        for path in paths:
            cur_lat = None
            cur_lon = None
            for c in path:  # c is a connection
                tail_time = time_ut - self.tail_seconds
                if tail_time > c.arrival_time or time_ut < c.departure_time:
                    # Connection is not currently "active" -> omit this connection.
                    continue

                # overlap_start ~ tail time
                # overlap_end ~ real time

                # Computing the overlap with the connection while considering the tail:
                overlap_start = max(c.departure_time, min(c.arrival_time, tail_time))
                overlap_end = max(c.departure_time, min(c.arrival_time, time_ut))

                c_duration = c.arrival_time - c.departure_time

                frac_start = 0
                frac_end = 1
                if c_duration > 0:
                    frac_start = (overlap_start - c.departure_time) / c_duration
                    frac_end = (overlap_end - c.departure_time) / c_duration

                assert (0 <= frac_start <= 1), (frac_start, c_duration)
                assert (0 <= frac_end <= 1), (frac_end, c_duration)

                tail_lon = c.from_lon + frac_start * (c.to_lon - c.from_lon)
                tail_lat = c.from_lat + frac_start * (c.to_lat - c.from_lat)

                real_lon = c.from_lon + frac_end * (c.to_lon - c.from_lon)
                real_lat = c.from_lat + frac_end * (c.to_lat - c.from_lat)

                ax.plot([tail_lon, real_lon], [tail_lat, real_lat], color=ROUTE_TYPE_TO_COLOR[c.route_type])
                cur_lat = real_lat
                cur_lon = real_lon

            if cur_lat is None:
                # Each path's connections do not always cover the whole time-span of the path.
                # Thus, if end_lat is not defined
                try:
                    path_still_active = (path[-1].arrival_time > time_ut - self.tail_seconds)
                    if path_still_active:
                        c = next(c for c in path[-1::-1] if c.arrival_time < time_ut)
                        cur_lat = c.to_lat
                        cur_lon = c.to_lon
                except StopIteration:
                    pass
            if self.path_markers and (cur_lat and cur_lon):
                ax.scatter([cur_lon], [cur_lat], "o", color="#636363", s=8)
