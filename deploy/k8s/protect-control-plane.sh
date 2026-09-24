#!/bin/sh
set -eu
interface=$(ip -4 route show default | awk 'NR==1 {print $5}')
test -n "$interface"
iptables -C INPUT -i "$interface" -p tcp -m multiport --dports 6443,10250,2379,2380 -j DROP 2>/dev/null ||
    iptables -I INPUT 1 -i "$interface" -p tcp -m multiport --dports 6443,10250,2379,2380 -j DROP
iptables -C INPUT -i "$interface" -p udp -m multiport --dports 8472,51820,51821 -j DROP 2>/dev/null ||
    iptables -I INPUT 1 -i "$interface" -p udp -m multiport --dports 8472,51820,51821 -j DROP
ip6tables -C INPUT -i "$interface" -p tcp -m multiport --dports 6443,10250,2379,2380 -j DROP 2>/dev/null ||
    ip6tables -I INPUT 1 -i "$interface" -p tcp -m multiport --dports 6443,10250,2379,2380 -j DROP
ip6tables -C INPUT -i "$interface" -p udp -m multiport --dports 8472,51820,51821 -j DROP 2>/dev/null ||
    ip6tables -I INPUT 1 -i "$interface" -p udp -m multiport --dports 8472,51820,51821 -j DROP
